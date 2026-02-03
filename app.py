# app.py

from datetime import datetime
import json
import pandas as pd
import plotly.graph_objects as go
import plotly.utils
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask import Flask, render_template, request, redirect, url_for, flash, get_flashed_messages
from flask import send_file
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import secrets
import string
from constants import PSR_TEMPLATES, PSR_DYNAMIC_TEMPLATES, get_psr_meta


# --- LIST OF NIGERIAN STATES ---
NIGERIAN_STATES = [
    'Abia', 'Adamawa', 'Akwa Ibom', 'Anambra', 'Bauchi', 'Bayelsa', 'Benue', 
    'Borno', 'Cross River', 'Delta', 'Ebonyi', 'Edo', 'Ekiti', 'Enugu', 
    'Gombe', 'Imo', 'Jigawa', 'Kaduna', 'Kano', 'Katsina', 'Kebbi', 
    'Kogi', 'Kwara', 'Lagos', 'Nasarawa', 'Niger', 'Ogun', 'Ondo', 
    'Osun', 'Oyo', 'Plateau', 'Rivers', 'Sokoto', 'Taraba', 'Yobe', 'Zamf', 
    'FCT - Abuja' # Include the Federal Capital Territory
]
# ------------------------------

# --- MASTER LIST OF ALL 19 PSR TEMPLATE TYPES ---
REPORT_TYPES = list(PSR_TEMPLATES.keys())

# --- MASTER LIST OF TARGETS FOR TEMPLATE 2 ---
TARGETS_ACHIEVED_LIST = [
    'Number of enforcement operations carried out (S&I, Zones, Lagos Office)',
    'Number of surveillance operations carried out (S&I, Zones, Lagos Office.)',
    'Number of Desk Offices set up for monitoring of markets in Nigeria (S&I, Zones, Lagos Office)',
    'Number of sales promotions registered and monitored (S&I)',
    'Number of consumer complaints received (S&I, Zones, Lagos Office)',
    'Number of consumer complaints resolved (S&I, Zones, Lagos Office)',
    'Average time(days) taken for resolution of a complaint (S&I, Zones, Lagos Office)',
    'Number of sub-standard/ fake products detected (items) (S&I, Zones, Lagos Office)',
    'Number of quality checks carried out (QA&D, Zones, Lagos Office)',
    'Number of quality reports sent to industries/service providers (QA&D, Zones, Lagos Office)',
    'Number of public alerts released (QA&D, CBE & PRU)',
    'Number of consumer sensitization campaigns carried out in electronic media (CBE, Zones, Lagos Office)',
    'Number of consumer programmes carried out in electronic media (CBE, Zones, Lagos Office)',
    'Frequency of consumer education programmes carried out in electronic media (total air in hours) (CBE, Zones, Lagos Office)',
    'Number of Consumer Information and Response Centers set up. (S&I CP, Zones & Lagos Office)'
]

# 1. Initialize the Flask Application
app = Flask(__name__)
# ...

# --- NEW CONFIGURATION START ---

# Tell Flask where the SQLite database file will be stored.
# 'sqlite:///project.db' means a file named 'project.db' in the project directory.
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///project.db'

# Disable a deprecation warning (good practice)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# --- NEW: Add a secret key for session management and flashing messages ---
app.config['SECRET_KEY'] = 'a_very_secret_key_that_should_be_complex_in_production'

# --- NEW CONFIGURATION END ---

# app.py (New Charting Function)

def create_price_trend_chart(reports):
    # Convert the list of PriceReport objects into a Pandas DataFrame
    # This is the fastest way to aggregate and group data
    df = pd.DataFrame([r.__dict__ for r in reports])

    # If the reports list is empty, return an empty figure
    if df.empty:
        return None

    # Clean up the date to just the date part (ignoring the time)
    df['date_only'] = df['date_recorded'].dt.date
    
    # Calculate the average price per day
    daily_avg_price = df.groupby('date_only')['price'].mean().reset_index()

    # --- Plotly Chart Creation ---
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=daily_avg_price['date_only'],
        y=daily_avg_price['price'],
        mode='lines+markers',
        name='Average Price (NGN)',
        line=dict(color='#007bff')
    ))

    # Configure the chart layout
    fig.update_layout(
        title_text='Average Price Trend Over Time',
        xaxis_title='Date Recorded',
        yaxis_title='Average Price (NGN)',
        hovermode='x unified',
        margin=dict(l=20, r=20, t=60, b=20)
    )

    # Convert the Plotly figure object into a JSON string
    # This is the format the HTML template will use to render the chart
    chart_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    return chart_json

# START: USER AUTHENTICATION & DATABASE MODELS (All models go here)


class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False) # Used for login
    password_hash = db.Column(db.String(128), nullable=False)
    # Role hierarchy:
    # 1 = Agent
    # 2 = Supervisor
    # 3 = Director
    # 4 = EVC
    # 9 = Admin
    role = db.Column(db.Integer, default=1)
    is_enabled = db.Column(db.Boolean, default=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    sex = db.Column(db.String(10), nullable=False)
    fccpc_office = db.Column(db.String(100), nullable=False)
    # Link reports to the agent who submitted them
    reports = db.relationship('PriceReport', backref='reporter', lazy=True) 

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == 9

    def is_supervisor(self):
        return self.role >= 2

    def is_director(self):
        return self.role >= 3

    def is_evc(self):
        return self.role >= 4
    
    def is_active(self):
        return self.is_enabled

# We need to link reports to the user. UPDATE the PriceReport Model!
# In the PriceReport class, add a foreign key:
# user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

# 2. Initialize Flask-Migrate
migrate = Migrate(app, db)

# Organized PriceReport model

class PriceReport(db.Model):
    # Optional: table name for clarity
    __tablename__ = 'price_reports'
    
    # 1. Primary and Foreign Keys
    id = db.Column(db.Integer, primary_key=True)
    # This links the report to the user who submitted it
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # 2. Core Data Fields
    agent_name = db.Column(db.String(80), nullable=False)
    product_name = db.Column(db.String(100), nullable=False)
    market_location = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(50), nullable=False)
    
    # 3. Timestamp
    # This automatically records the time of creation
    date_recorded = db.Column(db.DateTime, default=db.func.now())

    # This method is used for printing the object for easy debugging
    def __repr__(self):
        return f'<Report {self.id}: {self.product_name} at {self.price}>'
    

# app.py (New Database Model for Program Status)

# app.py (Replace your current ProgramReport class with this)

class ProgramReport(db.Model):
    __tablename__ = 'program_reports'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    report_type = db.Column(db.String(150), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    period_covered = db.Column(db.String(100), nullable=True)
    objective = db.Column(db.Text, nullable=True)
    date_started = db.Column(db.Date, nullable=True)
    previous_status_percentage = db.Column(db.Integer, default=0)
    
    # Common text fields for all reports
    status_details = db.Column(db.Text, nullable=True)       # Part A: Details of achievement
    constraints_requirements = db.Column(db.Text)             # Part B: Constraints
    status_percentage = db.Column(db.Integer, default=0)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

    agent = db.relationship('User', backref=db.backref('program_reports', lazy=True))
    
    # NEW: Relationship to specific report types (Template 2)
    targets_report = db.relationship('TargetsAchievedReport', uselist=False, backref='base_report')
    
    psr_rows = db.relationship("PSRRow", backref="program_report", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ProgramReport {self.id}: {self.title} - {self.report_type}>"

class ConsumerComplaint(db.Model):
    __tablename__ = 'consumer_complaints'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), nullable=False, default='RECEIVED')
    
    # Common Fields
    case_file_no = db.Column(db.String(50), nullable=False, unique=True)
    sector_category = db.Column(db.String(100))
    date_received = db.Column(db.DateTime, nullable=False) 
    complaint_details = db.Column(db.Text, nullable=False) 
    complainant_details = db.Column(db.Text, nullable=False) 
    respondent_details = db.Column(db.Text, nullable=False) 
    
    # Template-Specific Fields (Updated)
    action_taken = db.Column(db.Text)          # Col 7 (T3, T4)
    status_of_complaint = db.Column(db.Text)   # Col 8 (T3)
    value_of_complaint = db.Column(db.String(255)) # Col 9 (T3) or Col 8 (T4, T5) - Now a String for Remarks
    date_of_resolution = db.Column(db.DateTime) # Col 7 (T5)
    complainant_remark = db.Column(db.Text)    # Col 9 (T5)

    def __repr__(self):
        return f'<Complaint {self.case_file_no}: {self.status}>'
    
class TargetsAchievedReport(db.Model):
    __tablename__ = 'targets_achieved_reports'
    # This ID is the foreign key linking to the base report
    id = db.Column(db.Integer, db.ForeignKey('program_reports.id'), primary_key=True) 
    
    # Template 2 Unique Fields
    target_description = db.Column(db.Text, nullable=False)
    achievement_value = db.Column(db.Integer, default=0)
    target_remarks = db.Column(db.Text)
    
    def __repr__(self):
        return f"TargetsAchievedReport('{self.id}', Target: '{self.target_description}')"

class EnforcementOperation(db.Model):
    __tablename__ = "psr_enforcement_operations"

    id = db.Column(db.Integer, primary_key=True)

    program_report_id = db.Column(
        db.Integer,
        db.ForeignKey("program_reports.id"),
        nullable=False,
        unique=True
    )

    sector_classification = db.Column(db.String(255))
    date_commenced = db.Column(db.Date)
    date_completed = db.Column(db.Date)
    objectives = db.Column(db.Text)
    location_address = db.Column(db.Text)
    action_taken = db.Column(db.Text)

    item_description_qty = db.Column(db.Text)
    total_weight = db.Column(db.String(100))
    total_value = db.Column(db.String(100))

    remarks = db.Column(db.Text)

    program_report = db.relationship(
        "ProgramReport",
        backref=db.backref("enforcement_operation", uselist=False, cascade="all, delete-orphan")
    )
    
class PSRRow(db.Model):
    __tablename__ = "psr_rows"
    id = db.Column(db.Integer, primary_key=True)
    program_report_id = db.Column(db.Integer, db.ForeignKey("program_reports.id"), nullable=False)

    values = db.relationship("PSRFieldValue", backref="row", cascade="all, delete-orphan")


class PSRFieldValue(db.Model):
    __tablename__ = "psr_field_values"
    id = db.Column(db.Integer, primary_key=True)
    row_id = db.Column(db.Integer, db.ForeignKey("psr_rows.id"), nullable=False)

    field_key = db.Column(db.String(100), nullable=False)
    field_value = db.Column(db.Text)

class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)

    # Who performed the action
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # Who was affected (optional)
    target_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    action = db.Column(db.String(255), nullable=False)
    details = db.Column(db.Text)

    ip_address = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    actor = db.relationship("User", foreign_keys=[actor_id], backref="performed_actions")
    target = db.relationship("User", foreign_keys=[target_user_id], backref="actions_received")

    def __repr__(self):
        return f"<Audit {self.action} at {self.timestamp}>"
    
# class SeizureReport(db.Model):
#     __tablename__ = 'seizure_reports'
#     id = db.Column(db.Integer, db.ForeignKey('program_reports.id'), primary_key=True)
#     sector_classification = db.Column(db.String(100))
#     date_commenced = db.Column(db.Date)
#     date_completed = db.Column(db.Date)
#     objectives = db.Column(db.Text)
#     location_address = db.Column(db.Text)
#     action_taken = db.Column(db.Text)
#     # Column 7 Sub-fields
#     item_description_qty = db.Column(db.Text)
#     total_weight = db.Column(db.String(50))
#     total_value = db.Column(db.String(100))
#     remarks = db.Column(db.Text)

#     def __repr__(self):
#         # We use sector and item description so you can identify the report easily in the logs
#         return f"SeizureReport(ID: '{self.id}', Sector: '{self.sector_classification}', Item: '{self.item_description_qty}')"

login_manager = LoginManager()
login_manager.init_app(app)
# This sets the page users are redirected to if they try to access a protected page
login_manager.login_view = 'login' 
# Optional: A friendly message displayed when they are redirected
login_manager.login_message = 'Please log in to access this page.' 

# User loader function: tells Flask-Login how to find a user by their ID
@login_manager.user_loader
def load_user(user_id):
    # We'll define the User class next!
    return User.query.get(int(user_id))

# app.py (Inside register function)
# -------------------------------------------------------------------
# NEW: CUSTOM ADMIN ACCESS DECORATOR - PLACE IT HERE
# -------------------------------------------------------------------

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('Access denied: You must be an administrator.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def supervisor_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_supervisor():
            flash("Supervisor access required.", "danger")
            return redirect(url_for("program_dashboard"))
        return f(*args, **kwargs)
    return decorated

def log_action(action, target_user=None, details=None):
    try:
        log = AuditLog(
            actor_id=current_user.id if current_user.is_authenticated else None,
            target_user_id=target_user.id if target_user else None,
            action=action,
            details=details,
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
    except:
        db.session.rollback()
# -------------------------------------------------------------------

# NOW you can define the admin routes and use the decorator:

@app.route('/admin')
@admin_required
def admin_dashboard():
    role = request.args.get("role")
    search = request.args.get("search")

    query = User.query

    if role:
        query = query.filter(User.role == int(role))

    if search:
        query = query.filter(
            User.name.ilike(f"%{search}%") |
            User.email.ilike(f"%{search}%")
        )

    users = query.order_by(User.id.desc()).all()
    return render_template("admin_dashboard.html", users=users)

@app.route('/admin/reset/<int:user_id>', methods=['POST'])
@admin_required
def reset_password(user_id):
    # Retrieve the user to be reset
    user = User.query.get_or_404(user_id)

    # 1. Generate a secure, temporary password (10 characters)
    characters = string.ascii_letters + string.digits
    temp_password = ''.join(secrets.choice(characters) for i in range(10))

    # 2. Update the user's password hash
    user.set_password(temp_password)
    db.session.commit()
    
    log_action(
        action="Password Reset",
        target_user=user,
        details=f"Admin reset password for {user.email}"
    )

    # 3. Flash the temporary password to the ADMIN for IT support purposes
    flash(f"Password for **{user.name} ({user.email})** has been reset. New Temporary Password: **{temp_password}**", 'warning')
    
    return redirect(url_for('admin_dashboard'))


# app.py (New Route for Admin Role Assignment)

@app.route('/elevate_user/<int:user_id>/<int:new_role>')
@admin_required
def elevate_user(user_id, new_role):
    user = User.query.get_or_404(user_id)

    # Prevent admin from changing their own role
    if user.id == current_user.id:
        flash("You cannot change your own role.", "danger")
        return redirect(url_for("admin_dashboard"))

    if new_role not in [1, 2, 3, 4, 9]:
        flash("Invalid role selected.", "danger")
        return redirect(url_for("admin_dashboard"))

    old_role = user.role
    user.role = new_role

    db.session.commit()

    log_action(
        action="Role Changed",
        target_user=user,
        details=f"Role changed from {old_role} to {new_role}"
    )

    try:
        db.session.commit()
        flash(f"{user.name} role updated successfully.", "success")
    except:
        db.session.rollback()
        flash("Role update failed.", "danger")

    return redirect(url_for("admin_dashboard"))


@app.route('/register', methods=['GET', 'POST'])
def register():
    # Only allow registration if no users exist (initial admin setup)
    if User.query.count() > 0 and not current_user.is_authenticated:
        flash('Registration is currently restricted. Please contact an Admin.', 'warning')
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        # --- CAPTURE NEW FIELDS ---
        name = request.form['name']
        sex = request.form['sex']
        fccpc_office = request.form['fccpc_office']
        # --------------------------

        if User.query.filter_by(email=email).first():
            flash('Email already registered!', 'danger')
            return redirect(url_for('register'))
            
        new_user = User(
            email=email,
            name=name,
            sex=sex,
            fccpc_office=fccpc_office,
            is_enabled=True
        )
        new_user.set_password(password)
        
        # Keep initial admin logic (first user is Admin)
        if User.query.count() == 0:
            new_user.role = 9 # Admin
            flash('Initial Admin account created! Please log in.', 'success')
        else:
            flash('Agent account created! You can now log in.', 'success')

        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
        
    return render_template('register.html', states=NIGERIAN_STATES)

# Login Route and Template

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('program_dashboard')) 
        
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        
        if user and user.check_password(request.form['password']):

            if not user.is_enabled:
                flash("Your account has been suspended. Contact administrator.", "danger")
                return redirect(url_for("login"))

            login_user(user)

            log_action(
                action="Login",
                details=f"{user.email} logged in"
            )

            flash('Logged in successfully!', 'success')
            return redirect(url_for('program_dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    log_action(
        action="Logout",
        details=f"{current_user.email} logged out"
    )

    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# 2. Define the main route (The Dashboard)
# app.py (Updated dashboard function for SEARCH/FILTER)

@app.route('/', methods=['GET'])
@login_required
def dashboard():
    search_term = request.args.get('search') # Capture the search query

    # Start with the base query for all reports
    query = PriceReport.query.order_by(PriceReport.date_recorded.desc())

    # --- APPLY SEARCH FILTER ---
    if search_term:
        # Use .ilike for case-insensitive partial match on product_name
        query = query.filter(PriceReport.product_name.ilike(f'%{search_term}%'))

    # 1. Fetch reports based on role (Admin vs. Agent)
    if current_user.is_admin():
        reports = query.all() # Admins see all filtered results
        view_title = "Admin View (All Reports)"
    else:
        # Agents see only their own filtered results
        reports = query.filter_by(user_id=current_user.id).all() 
        view_title = f"Agent View (Your Reports - {current_user.name})" 

    # 2. Generate the chart data (Must pass the request object too)
    price_trend_chart_json = create_price_trend_chart(reports)

    # 3. Render the template
    return render_template(
        'dashboard.html', 
        data=reports, 
        view_title=view_title, 
        price_trend_chart_json=price_trend_chart_json,
        request=request # PASS THE REQUEST OBJECT for the form to work
    )
    
    
# app.py (New route for displaying the form)

@app.route('/report')
@login_required
def report_form():
    """Renders the HTML form for data entry."""
    # It just loads and displays the report_form.html file
    return render_template('report_form.html')

# app.py (New route for handling form submission)

@app.route('/submit', methods=['POST'])  # Only responds to POST requests from the form
@login_required
def submit_report():
    # Get the data submitted via the form
    if request.method == 'POST':
        # Collect data from the form fields using their 'name' attributes
        # 1. Automatically get the agent name from the logged-in user
        agent_name = current_user.name
        # 2. Collect other data from the form fields
        product_name = request.form['product_name']
        market_location = request.form['market_location']
        price = float(request.form['price']) # Convert to a floating point number
        unit = request.form['unit']

        # Create a new PriceReport object
        new_report = PriceReport(
            agent_name=agent_name, # Use the automated name
            product_name=product_name,
            market_location=market_location,
            price=price,
            unit=unit,
            # NEW: Link the report to the currently logged-in user
            user_id=current_user.id
        )

        try:
            # Add the new object to the database session
            db.session.add(new_report)
            # Commit the changes
            db.session.commit()

            # --- NEW: Flash a success message ---
            flash(f'Report for "{product_name}" saved successfully!', 'success')

            # Redirect the user back to the dashboard
            return redirect(url_for('dashboard'))
        except:
            # Basic error handling
            db.session.rollback()
            return "There was an issue submitting your report.", 500 # Return an error status

    # If someone tries to visit /submit directly (GET), send them back to the form
    return redirect(url_for('report_form'))

# app.py (New Route for Deleting Reports - Add this to your routes section)

@app.route('/delete/<int:report_id>', methods=['POST'])
@admin_required # Only admins can delete reports
def delete_report(report_id):
    # Get the report by its ID, or return 404 if not found
    report_to_delete = PriceReport.query.get_or_404(report_id)

    try:
        db.session.delete(report_to_delete)
        db.session.commit()
        
        log_action(
            action="Price Report Deleted",
            details=f"Deleted report ID {report_id} ({report_to_delete.product_name})"
        )
        
        flash(f'Report ID {report_id} ({report_to_delete.product_name}) deleted successfully.', 'danger')
        return redirect(url_for('dashboard'))
    except:
        db.session.rollback()
        flash('An error occurred during report deletion.', 'danger')
        return redirect(url_for('dashboard'))
    
    
# app.py (New Route for Editing Reports - Add this to your routes section)

@app.route('/edit/<int:report_id>', methods=['GET', 'POST'])
@admin_required # Only admins can edit reports
def edit_report(report_id):
    report = PriceReport.query.get_or_404(report_id)
    
    global NIGERIAN_STATES
    
    if request.method == 'POST':
        # 1. Update the object properties with new form data
        # IMPORTANT: The agent_name is NOT updated as it is tied to the submitting user
        report.product_name = request.form['product_name']
        report.market_location = request.form['market_location']
        report.price = float(request.form['price'])
        report.unit = request.form['unit']
        
        try:
            # 2. Commit the changes to the database
            db.session.commit()
            flash(f'Report ID {report_id} updated successfully!', 'success')
            return redirect(url_for('dashboard'))
        except:
            db.session.rollback()
            flash('An error occurred while updating the report.', 'danger')
            return redirect(url_for('dashboard'))

    # GET request: Render the pre-filled form
    return render_template(
        'report_form.html', 
        report=report, # Pass the report object
        states=NIGERIAN_STATES, # Pass the states list
        form_title=f"Edit Report ID {report_id} by {report.agent_name}"
    )


# app.py (New Route for Program Status Submission)

@app.route('/psr/submit', methods=['GET', 'POST'])
@login_required 
def program_report_form():
    if request.method == 'POST':
        report_type = request.form.get("report_type")
        template_slug = request.form.get("report_type")

        if not template_slug:
            flash("No report template selected.", "danger")
            return render_template(
                "program_report_form.html",
                report_types=REPORT_TYPES,
                targets_list=TARGETS_ACHIEVED_LIST,
                psr_templates=PSR_TEMPLATES
            )

        # ====================================================================
        # --- SECTION 1: TEMPLATES 3, 4, 5 (Consumer Complaints) ---
        # ====================================================================
        if template_slug.startswith("complaints_"):
            
            case_file_no = request.form.get('case_file_no', '').strip()
            if not case_file_no:
                flash('Case File No. is required.', 'danger')
                return render_template( 'program_report_form.html', report_types=REPORT_TYPES, targets_list=TARGETS_ACHIEVED_LIST, psr_templates=PSR_TEMPLATES )
            
            if ConsumerComplaint.query.filter_by(case_file_no=case_file_no).first():
                flash(f'Error: Case File No. {case_file_no} already exists.', 'danger')
                return render_template(
    'program_report_form.html',
    report_types=REPORT_TYPES,
    targets_list=TARGETS_ACHIEVED_LIST,
    psr_templates=PSR_TEMPLATES,
    dynamic_templates=PSR_DYNAMIC_TEMPLATES
)

            # Capture common Complaint fields
            c_name = request.form.get('complainant_name', '')
            c_addr = request.form.get('complainant_address', '')
            c_email = request.form.get('complainant_email', '')
            c_phone = request.form.get('complainant_phone', '')
            complainant_details = f"Name: {c_name}\nAddress: {c_addr}\nEmail: {c_email}\nPhone: {c_phone}"

            r_name = request.form.get('respondent_name', '')
            r_addr = request.form.get('respondent_address', '')
            respondent_details = f"Name: {r_name}\nAddress: {r_addr}"

            # Specialized Complaint logic
            # Default values (Template 3 – complaints_received)
            complaint_status = "RECEIVED"
            action_taken = request.form.get("action_taken")
            date_of_resolution = None
            complainant_remark = None
            value_of_complaint = request.form.get("value_of_complaint")

            # Template 4 – Ongoing Complaints
            if template_slug == "complaints_ongoing":
                complaint_status = "ONGOING"
                action_taken = request.form.get("action_taken_combined")
                value_of_complaint = request.form.get("value_of_complaint_t4")
                
            # Template 5 – Resolved Complaints
            elif template_slug == "complaints_resolved":
                complaint_status = "RESOLVED"
                res_date_str = request.form.get("date_of_resolution")
                date_of_resolution = (
                    datetime.fromisoformat(res_date_str) if res_date_str else None
                )
                value_of_complaint = request.form.get("value_remarks")
                complainant_remark = request.form.get("complainant_remark")

            new_complaint = ConsumerComplaint(
                user_id=current_user.id,
                status=complaint_status,
                case_file_no=case_file_no,
                sector_category=request.form.get('sector_category'),
                date_received=datetime.fromisoformat(request.form.get('date_received')) if request.form.get('date_received') else datetime.utcnow(),
                complaint_details=request.form.get('complaint_details'),
                complainant_details=complainant_details,
                respondent_details=respondent_details,
                action_taken=action_taken,
                status_of_complaint=request.form.get('status_date_time'),
                value_of_complaint=value_of_complaint,
                date_of_resolution=date_of_resolution,
                complainant_remark=complainant_remark
            )

            try:
                db.session.add(new_complaint)
                db.session.commit()
                flash(f'Case {case_file_no} submitted!', 'success')
                return redirect(url_for('program_dashboard'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error: {e}', 'danger')
                return render_template(
    'program_report_form.html',
    report_types=REPORT_TYPES,
    targets_list=TARGETS_ACHIEVED_LIST,
    psr_templates=PSR_TEMPLATES,
    dynamic_templates=PSR_DYNAMIC_TEMPLATES
)

        # ====================================================================
        # --- SECTION 2: PROGRAM REPORTS (Template 1, 2, 6, etc.) ---
        # ====================================================================
        
        # FIX: We use .get() with defaults so hidden fields don't cause KeyErrors
        meta = get_psr_meta(report_type)
        default_title = f"{meta['title']} Report"
        title = request.form.get('title') or default_title
        objective = request.form.get('objective') or "N/A"
        status_details = request.form.get('status_details') or "Specialized data submitted."
        
        # Handle Date Started safely
        ds_str = request.form.get('date_started')
        date_started = datetime.strptime(ds_str, '%Y-%m-%d').date() if ds_str else datetime.utcnow().date()

        new_report = ProgramReport(
            user_id=current_user.id,
            report_type=report_type,
            title=title,
            objective=objective,
            period_covered=request.form.get('period_covered', 'N/A'),
            date_started=date_started,
            previous_status_percentage=int(request.form.get('previous_status_percentage', 0)),
            status_percentage=int(request.form.get('status_percentage', 0)),
            status_details=status_details,
            constraints_requirements=request.form.get('constraints', 'None')
        )

        try:
            db.session.add(new_report)
            db.session.flush() 

            # Template 2 – Targets Achieved
            if template_slug == "targets_achieved":
                target_selection = request.form.get("target_select")
                final_target = (
                    request.form.get("target_description_manual")
                    if target_selection == "Other"
                    else target_selection
                )

                db.session.add(
                    TargetsAchievedReport(
                        id=new_report.id,
                        target_description=final_target or "N/A",
                        achievement_value=int(request.form.get("achievement_value", 0)),
                        target_remarks=request.form.get("target_remarks", "None"),
                    )
                )

            # Template 6 – Enforcement Operations
            elif template_slug == "enforcement_operations":
                def safe_date(field):
                    v = request.form.get(field)
                    return datetime.strptime(v, "%Y-%m-%d").date() if v else None

                db.session.add(
                    EnforcementOperation(
                        program_report_id=new_report.id,
                        sector_classification=request.form.get("seizure_sector"),
                        date_commenced=safe_date("seizure_commenced"),
                        date_completed=safe_date("seizure_completed"),
                        location_address=request.form.get("seizure_location"),
                        item_description_qty=request.form.get("seizure_item_desc"),
                        total_value=request.form.get("seizure_value"),
                        action_taken=request.form.get("seizure_action"),
                        remarks=request.form.get("seizure_remarks"),
                    )
                )
                
                # Templates 7–20 (Dynamic Engine)
            elif template_slug in PSR_DYNAMIC_TEMPLATES:
                template_config = PSR_DYNAMIC_TEMPLATES[template_slug]
                fields = template_config["fields"]

                rows_data = {}

                for field in fields:
                    key = field["key"]

                    # Try list (for future multi-row support)
                    values = request.form.getlist(key)

                    # Fallback to single input
                    if not values:
                        single = request.form.get(key)
                        values = [single] if single else []

                    rows_data[key] = values

                row_count = len(next(iter(rows_data.values()), []))

                for i in range(row_count):
                    new_row = PSRRow(program_report_id=new_report.id)
                    db.session.add(new_row)
                    db.session.flush()

                    for field in fields:
                        value = rows_data[field["key"]][i]

                        db.session.add(
                            PSRFieldValue(
                                row_id=new_row.id,
                                field_key=field["key"],
                                field_value=value
                            )
                        )

            db.session.commit()
            flash("Report submitted successfully!", 'success')
            return redirect(url_for('program_dashboard'))
        

        except Exception as e:
            db.session.rollback()
            print(f"DEBUG ERROR: {e}")
            flash(f"Submission Error: {e}", 'danger')
            return render_template(
    'program_report_form.html',
    report_types=REPORT_TYPES,
    targets_list=TARGETS_ACHIEVED_LIST,
    psr_templates=PSR_TEMPLATES,
    dynamic_templates=PSR_DYNAMIC_TEMPLATES
)

    return render_template(
    'program_report_form.html',
    report_types=REPORT_TYPES,
    targets_list=TARGETS_ACHIEVED_LIST,
    psr_templates=PSR_TEMPLATES,
    dynamic_templates=PSR_DYNAMIC_TEMPLATES
)

# 2. Add a NEW program dashboard route to app.py
@app.route('/psr/dashboard')
@login_required
def program_dashboard():
    template_filter = request.args.get("template")
    search = request.args.get("search")

    query = ProgramReport.query

    # Admin / Director / EVC see everything
    if current_user.is_admin() or current_user.is_director() or current_user.is_evc():
        pass  

    # Supervisor sees only reports from same office
    elif current_user.is_supervisor():
        query = query.join(User).filter(
            User.fccpc_office == current_user.fccpc_office
        )

    # Agent sees only own reports
    else:
        query = query.filter(ProgramReport.user_id == current_user.id)

    if template_filter:
        query = query.filter(ProgramReport.report_type == template_filter)

    if search:
        query = query.filter(ProgramReport.title.ilike(f"%{search}%"))

    reports = query.order_by(ProgramReport.date_created.desc()).all()

    for report in reports:
        report.psr_meta = get_psr_meta(report.report_type)

    return render_template(
        "program_dashboard.html",
        reports=reports,
        templates=PSR_TEMPLATES,
        view_title="Program Status Reports"
    )

@app.route('/complaints_dashboard')
@login_required
def complaints_dashboard():
    """Fetches and displays all consumer complaints, categorized by status."""
    
    # 1. Fetch all complaints, sorted by the date they were received
    # (ConsumerComplaint model must be imported/defined above)
    all_complaints = ConsumerComplaint.query.order_by(ConsumerComplaint.date_received.desc()).all()
    
    # 2. Organize complaints by status for display
    complaints_by_status = {
        'RECEIVED': [],
        'ONGOING': [],
        'RESOLVED': []
    }
    
    for complaint in all_complaints:
        status = complaint.status.upper()
        if status in complaints_by_status:
            complaints_by_status[status].append(complaint)
        # Handle complaints with unexpected status by grouping them under 'RECEIVED'
        else:
            complaints_by_status['RECEIVED'].append(complaint) 
            
    # 3. Calculate status counts for quick statistics
    total_count = len(all_complaints)
    received_count = len(complaints_by_status['RECEIVED'])
    ongoing_count = len(complaints_by_status['ONGOING'])
    resolved_count = len(complaints_by_status['RESOLVED'])
    
    return render_template('complaints_dashboard.html', 
                           complaints_by_status=complaints_by_status,
                           total_count=total_count,
                           received_count=received_count,
                           ongoing_count=ongoing_count,
                           resolved_count=resolved_count,
                           title="Consumer Complaints Dashboard")

@app.route('/psr/view/<int:report_id>')
@login_required
def view_program_report(report_id):
    report = ProgramReport.query.get_or_404(report_id)

    if not current_user.is_admin() and report.user_id != current_user.id:
        flash('You are not authorized to view this report.', 'danger')
        return redirect(url_for('program_dashboard'))

    template_slug = report.report_type

    # ========== HANDLE DYNAMIC TEMPLATES (7–20) ==========
    if template_slug in PSR_DYNAMIC_TEMPLATES:
        config = PSR_DYNAMIC_TEMPLATES[template_slug]

        rows = []
        for row in report.psr_rows:
            row_data = {}
            for value in row.values:
                row_data[value.field_key] = value.field_value
            rows.append(row_data)

        return render_template(
            "psr_views/dynamic.html",
            report=report,
            config=config,
            rows=rows
        )

    # ========== NORMAL TEMPLATES (1–6) ==========
    return render_template(
        f"psr_views/{template_slug}.html",
        report=report
    )

@app.route('/psr/delete/<int:report_id>', methods=['POST'])
@login_required
def delete_program_report(report_id):
    report = ProgramReport.query.get_or_404(report_id)

    # Security check
    if not current_user.is_admin() and report.user_id != current_user.id:
        flash("You are not authorized to delete this report.", "danger")
        return redirect(url_for('program_dashboard'))

    try:
        db.session.delete(report)
        db.session.commit()
        flash("Report deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Delete failed: {e}", "danger")

    return redirect(url_for('program_dashboard'))


@app.route('/psr/export_csv')
@login_required # Only logged-in users can export
def export_psr_data():
    # 1. Fetch all program reports (Admins get all, Agents get their own)
    if current_user.is_admin():
        reports = ProgramReport.query.order_by(ProgramReport.date_created.desc()).all()
    else:
        # Agents can only export their own reports
        reports = ProgramReport.query.filter_by(user_id=current_user.id).order_by(ProgramReport.date_created.desc()).all()

    # 2. Start building the CSV content
    # Define the header row to include all necessary fields
    csv_data = "ID,Report Type,Title,Period Covered,Objective,Status Details,Achievement (%),Date Created,Agent Name\n"
    
    # 3. Populate CSV rows
    for report in reports:
        # Clean up details to handle commas/newlines in status_details (using replace)
        details = report.status_details.replace('\n', ' ').replace(',', ';') 
        
        row = f"{report.id},"
        # FIX THE SYNTAX ERROR HERE: Combine the f-strings correctly
        row += f"{report.report_type},"
        row += f"\"{report.title}\"," # Ensure title is quoted for safety
        row += f"{report.period_covered},"
        row += f"{report.objective},"
        row += f"\"{details}\"," # Quoting the field protects text with special characters
        row += f"{report.status_percentage},"
        row += f"{report.date_created.strftime('%Y-%m-%d %H:%M')},"
        row += f"{report.agent.name}\n" # Use 'report.agent.name'
        csv_data += row

    # 4. Prepare a temporary file to send back
    from io import BytesIO
    buffer = BytesIO()
    buffer.write(csv_data.encode('utf-8'))
    buffer.seek(0)
    
    # 5. Send the file to the user
    return send_file(
        buffer,
        as_attachment=True,
        download_name='PSR_Export.csv',
        mimetype='text/csv'
    )

@app.route("/psr/export/<int:report_id>")
@login_required
def export_single_psr(report_id):
    report = ProgramReport.query.get_or_404(report_id)

    # Security check
    if not current_user.is_admin() and report.user_id != current_user.id:
        abort(403)

    # Only dynamic templates are exportable
    if report.report_type not in PSR_DYNAMIC_TEMPLATES:
        flash("Export only available for dynamic templates", "warning")
        return redirect(url_for("view_program_report", report_id=report.id))

    config = PSR_DYNAMIC_TEMPLATES[report.report_type]
    fields = config["fields"]

    import csv
    from io import StringIO
    from flask import Response

    output = StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([f["label"] for f in fields])

    # Data rows (correct structure)
    for row in report.psr_rows:
        row_dict = {v.field_key: v.field_value for v in row.values}
        writer.writerow([row_dict.get(f["key"], "") for f in fields])

    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=psr_{report.id}.csv"
        },
    )

@app.route("/admin/audit-logs")
@admin_required
def audit_logs():
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(500).all()

    return render_template(
        "audit_logs.html",
        logs=logs
    )

@app.route('/admin/toggle-user/<int:user_id>', methods=['POST'])
@admin_required
def toggle_user_status(user_id):
    user = User.query.get_or_404(user_id)

    user.is_enabled = not user.is_enabled
    db.session.commit()

    log_action(
        action="User Status Changed",
        target_user=user,
        details=f"Account {'re-activated' if user.is_enabled else 'suspended'}"
    )

    flash(
        f"User {'re-activated' if user.is_enabled else 'suspended'} successfully.",
        "success"
    )

    return redirect(url_for('admin_dashboard'))


            
@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500
    
# 5. Run the Application
if __name__ == '__main__':
    # 'app.run()' starts the server. debug=True makes it reload on changes.
    app.run(debug=True)