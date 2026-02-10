# app.py - UNIFIED STATS VERSION (PSR + Complaints Combined)

from datetime import datetime
import json, os
import pandas as pd
import plotly.graph_objects as go
import plotly.utils
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask import send_file
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from functools import wraps
import secrets
import string
from constants import PSR_TEMPLATES, PSR_DYNAMIC_TEMPLATES, get_psr_meta
from dotenv import load_dotenv
load_dotenv()


# --- LIST OF NIGERIAN STATES ---
NIGERIAN_STATES = [
    'Abia', 'Adamawa', 'Akwa Ibom', 'Anambra', 'Bauchi', 'Bayelsa', 'Benue', 
    'Borno', 'Cross River', 'Delta', 'Ebonyi', 'Edo', 'Ekiti', 'Enugu', 
    'Gombe', 'Imo', 'Jigawa', 'Kaduna', 'Kano', 'Katsina', 'Kebbi', 
    'Kogi', 'Kwara', 'Lagos', 'Nasarawa', 'Niger', 'Ogun', 'Ondo', 
    'Osun', 'Oyo', 'Plateau', 'Rivers', 'Sokoto', 'Taraba', 'Yobe', 'Zamfara', 
    'FCT - Abuja'
]

REPORT_TYPES = list(PSR_TEMPLATES.keys())

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

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'sqlite:///project.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

def create_price_trend_chart(reports):
    df = pd.DataFrame([r.__dict__ for r in reports])
    if df.empty:
        return None
    df['date_only'] = df['date_recorded'].dt.date
    daily_avg_price = df.groupby('date_only')['price'].mean().reset_index()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=daily_avg_price['date_only'],
        y=daily_avg_price['price'],
        mode='lines+markers',
        name='Average Price (NGN)',
        line=dict(color='#007bff')
    ))
    fig.update_layout(
        title_text='Average Price Trend Over Time',
        xaxis_title='Date Recorded',
        yaxis_title='Average Price (NGN)',
        hovermode='x unified',
        margin=dict(l=20, r=20, t=60, b=20)
    )
    chart_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    return chart_json

# DATABASE MODELS

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.Integer, default=1)
    is_enabled = db.Column(db.Boolean, default=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    sex = db.Column(db.String(10), nullable=False)
    fccpc_office = db.Column(db.String(100), nullable=False)
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

class PriceReport(db.Model):
    __tablename__ = 'price_reports'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    agent_name = db.Column(db.String(80), nullable=False)
    product_name = db.Column(db.String(100), nullable=False)
    market_location = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(50), nullable=False)
    date_recorded = db.Column(db.DateTime, default=db.func.now())

    def __repr__(self):
        return f'<Report {self.id}: {self.product_name} at {self.price}>'

class ProgramReport(db.Model):
    __tablename__ = 'program_reports'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='submitted', nullable=False)
    report_type = db.Column(db.String(150), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    period_covered = db.Column(db.String(100), nullable=True)
    objective = db.Column(db.Text, nullable=True)
    date_started = db.Column(db.Date, nullable=True)
    previous_status_percentage = db.Column(db.Integer, default=0)
    status_details = db.Column(db.Text, nullable=True)
    constraints_requirements = db.Column(db.Text)
    status_percentage = db.Column(db.Integer, default=0)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    agent = db.relationship('User', backref=db.backref('program_reports', lazy=True))
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
    case_file_no = db.Column(db.String(50), nullable=False, unique=True)
    sector_category = db.Column(db.String(100))
    date_received = db.Column(db.DateTime, nullable=False) 
    complaint_details = db.Column(db.Text, nullable=False) 
    complainant_details = db.Column(db.Text, nullable=False) 
    respondent_details = db.Column(db.Text, nullable=False) 
    action_taken = db.Column(db.Text)
    status_of_complaint = db.Column(db.Text)
    value_of_complaint = db.Column(db.String(255))
    date_of_resolution = db.Column(db.DateTime)
    complainant_remark = db.Column(db.Text)
    agent = db.relationship('User', backref=db.backref('consumer_complaints', lazy=True))

    def __repr__(self):
        return f'<Complaint {self.case_file_no}: {self.status}>'
    
class TargetsAchievedReport(db.Model):
    __tablename__ = 'targets_achieved_reports'
    id = db.Column(db.Integer, db.ForeignKey('program_reports.id'), primary_key=True) 
    target_description = db.Column(db.Text, nullable=False)
    achievement_value = db.Column(db.Integer, default=0)
    target_remarks = db.Column(db.Text)
    
    def __repr__(self):
        return f"TargetsAchievedReport('{self.id}', Target: '{self.target_description}')"

class EnforcementOperation(db.Model):
    __tablename__ = "psr_enforcement_operations"
    id = db.Column(db.Integer, primary_key=True)
    program_report_id = db.Column(db.Integer, db.ForeignKey("program_reports.id"), nullable=False, unique=True)
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
    program_report = db.relationship("ProgramReport", backref=db.backref("enforcement_operation", uselist=False, cascade="all, delete-orphan"))
    
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
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    target_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(255), nullable=False)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    actor = db.relationship("User", foreign_keys=[actor_id], backref="performed_actions")
    target = db.relationship("User", foreign_keys=[target_user_id], backref="actions_received")

    def __repr__(self):
        return f"<Audit {self.action} at {self.timestamp}>"

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' 
login_manager.login_message = 'Please log in to access this page.' 

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# DECORATORS

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

# ADMIN ROUTES

@app.route('/admin')
@admin_required
def admin_dashboard():
    role = request.args.get("role")
    search = request.args.get("search")
    query = User.query
    if role:
        query = query.filter(User.role == int(role))
    if search:
        query = query.filter(User.name.ilike(f"%{search}%") | User.email.ilike(f"%{search}%"))
    users = query.order_by(User.id.desc()).all()
    return render_template("admin_dashboard.html", users=users)

@app.route('/admin/reset/<int:user_id>', methods=['POST'])
@admin_required
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    characters = string.ascii_letters + string.digits
    temp_password = ''.join(secrets.choice(characters) for i in range(10))
    user.set_password(temp_password)
    db.session.commit()
    log_action(action="Password Reset", target_user=user, details=f"Admin reset password for {user.email}")
    flash(f"Password for **{user.name} ({user.email})** has been reset. New Temporary Password: **{temp_password}**", 'warning')
    return redirect(url_for('admin_dashboard'))

@app.route('/elevate_user/<int:user_id>/<int:new_role>')
@admin_required
def elevate_user(user_id, new_role):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You cannot change your own role.", "danger")
        return redirect(url_for("admin_dashboard"))
    if new_role not in [1, 2, 3, 4, 9]:
        flash("Invalid role selected.", "danger")
        return redirect(url_for("admin_dashboard"))
    old_role = user.role
    user.role = new_role
    db.session.commit()
    log_action(action="Role Changed", target_user=user, details=f"Role changed from {old_role} to {new_role}")
    try:
        db.session.commit()
        flash(f"{user.name} role updated successfully.", "success")
    except:
        db.session.rollback()
        flash("Role update failed.", "danger")
    return redirect(url_for("admin_dashboard"))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if User.query.count() > 0 and not current_user.is_authenticated:
        flash('Registration is currently restricted. Please contact an Admin.', 'warning')
        return redirect(url_for('login'))
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        name = request.form['name']
        sex = request.form['sex']
        fccpc_office = request.form['fccpc_office']
        if User.query.filter_by(email=email).first():
            flash('Email already registered!', 'danger')
            return redirect(url_for('register'))
        new_user = User(email=email, name=name, sex=sex, fccpc_office=fccpc_office, is_enabled=True)
        new_user.set_password(password)
        if User.query.count() == 0:
            new_user.role = 9
            flash('Initial Admin account created! Please log in.', 'success')
        else:
            flash('Agent account created! You can now log in.', 'success')
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html', states=NIGERIAN_STATES)

limiter = Limiter(app=app, key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
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
            log_action(action="Login", details=f"{user.email} logged in")
            flash('Logged in successfully!', 'success')
            return redirect(url_for('program_dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    log_action(action="Logout", details=f"{current_user.email} logged out")
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# PRICE REPORTS ROUTES

@app.route('/', methods=['GET'])
@login_required
def dashboard():
    search_term = request.args.get('search')
    query = PriceReport.query.order_by(PriceReport.date_recorded.desc())
    if search_term:
        query = query.filter(PriceReport.product_name.ilike(f'%{search_term}%'))
    if current_user.is_admin():
        reports = query.all()
        view_title = "Admin View (All Reports)"
    else:
        reports = query.filter_by(user_id=current_user.id).all() 
        view_title = f"Agent View (Your Reports - {current_user.name})" 
    price_trend_chart_json = create_price_trend_chart(reports)
    return render_template('dashboard.html', data=reports, view_title=view_title, price_trend_chart_json=price_trend_chart_json, request=request)

@app.route('/report')
@login_required
def report_form():
    return render_template('report_form.html')

@app.route('/submit', methods=['POST'])
@login_required
def submit_report():
    if request.method == 'POST':
        agent_name = current_user.name
        product_name = request.form['product_name']
        market_location = request.form['market_location']
        price = float(request.form['price'])
        unit = request.form['unit']
        new_report = PriceReport(agent_name=agent_name, product_name=product_name, market_location=market_location, price=price, unit=unit, user_id=current_user.id)
        try:
            db.session.add(new_report)
            db.session.commit()
            flash(f'Report for "{product_name}" saved successfully!', 'success')
            return redirect(url_for('dashboard'))
        except:
            db.session.rollback()
            return "There was an issue submitting your report.", 500
    return redirect(url_for('report_form'))

@app.route('/delete/<int:report_id>', methods=['POST'])
@admin_required
def delete_report(report_id):
    report_to_delete = PriceReport.query.get_or_404(report_id)
    try:
        db.session.delete(report_to_delete)
        db.session.commit()
        log_action(action="Price Report Deleted", details=f"Deleted report ID {report_id} ({report_to_delete.product_name})")
        flash(f'Report ID {report_id} ({report_to_delete.product_name}) deleted successfully.', 'danger')
        return redirect(url_for('dashboard'))
    except:
        db.session.rollback()
        flash('An error occurred during report deletion.', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/edit/<int:report_id>', methods=['GET', 'POST'])
@admin_required
def edit_report(report_id):
    report = PriceReport.query.get_or_404(report_id)
    global NIGERIAN_STATES
    if request.method == 'POST':
        report.product_name = request.form['product_name']
        report.market_location = request.form['market_location']
        report.price = float(request.form['price'])
        report.unit = request.form['unit']
        try:
            db.session.commit()
            flash(f'Report ID {report_id} updated successfully!', 'success')
            return redirect(url_for('dashboard'))
        except:
            db.session.rollback()
            flash('An error occurred while updating the report.', 'danger')
            return redirect(url_for('dashboard'))
    return render_template('report_form.html', report=report, states=NIGERIAN_STATES, form_title=f"Edit Report ID {report_id} by {report.agent_name}")

# PSR REPORT SUBMISSION

@app.route('/psr/submit', methods=['GET', 'POST'])
@login_required 
def program_report_form():
    if request.method == 'POST':
        action = request.form.get("action", "submit")
        is_draft = action == "draft"
        template_slug = report_type = request.form.get("report_type")

        if not template_slug:
            flash("No report template selected.", "danger")
            return render_template("program_report_form.html", report_types=REPORT_TYPES, targets_list=TARGETS_ACHIEVED_LIST, psr_templates=PSR_TEMPLATES)

        # COMPLAINT TEMPLATES
        if template_slug.startswith("complaints_"):
            case_file_no = request.form.get('case_file_no', '').strip()
            if not case_file_no:
                flash('Case File No. is required.', 'danger')
                return render_template('program_report_form.html', report_types=REPORT_TYPES, targets_list=TARGETS_ACHIEVED_LIST, psr_templates=PSR_TEMPLATES)
            if ConsumerComplaint.query.filter_by(case_file_no=case_file_no).first():
                flash(f'Error: Case File No. {case_file_no} already exists.', 'danger')
                return render_template('program_report_form.html', report_types=REPORT_TYPES, targets_list=TARGETS_ACHIEVED_LIST, psr_templates=PSR_TEMPLATES, dynamic_templates=PSR_DYNAMIC_TEMPLATES)

            c_name = request.form.get('complainant_name', '')
            c_addr = request.form.get('complainant_address', '')
            c_email = request.form.get('complainant_email', '')
            c_phone = request.form.get('complainant_phone', '')
            complainant_details = f"Name: {c_name}\nAddress: {c_addr}\nEmail: {c_email}\nPhone: {c_phone}"
            r_name = request.form.get('respondent_name', '')
            r_addr = request.form.get('respondent_address', '')
            respondent_details = f"Name: {r_name}\nAddress: {r_addr}"

            complaint_status = "RECEIVED"
            action_taken = request.form.get("action_taken")
            date_of_resolution = None
            complainant_remark = None
            value_of_complaint = request.form.get("value_of_complaint")

            if template_slug == "complaints_ongoing":
                complaint_status = "ONGOING"
                action_taken = request.form.get("action_taken_combined")
                value_of_complaint = request.form.get("value_of_complaint_t4")
            elif template_slug == "complaints_resolved":
                complaint_status = "RESOLVED"
                res_date_str = request.form.get("date_of_resolution")
                date_of_resolution = datetime.fromisoformat(res_date_str) if res_date_str else None
                value_of_complaint = request.form.get("value_remarks")
                complainant_remark = request.form.get("complainant_remark")

            new_complaint = ConsumerComplaint(
                user_id=current_user.id, status=complaint_status, case_file_no=case_file_no,
                sector_category=request.form.get('sector_category'),
                date_received=datetime.fromisoformat(request.form.get('date_received')) if request.form.get('date_received') else datetime.utcnow(),
                complaint_details=request.form.get('complaint_details'), complainant_details=complainant_details,
                respondent_details=respondent_details, action_taken=action_taken,
                status_of_complaint=request.form.get('status_date_time'), value_of_complaint=value_of_complaint,
                date_of_resolution=date_of_resolution, complainant_remark=complainant_remark
            )

            try:
                db.session.add(new_complaint)
                db.session.commit()
                if is_draft:
                    flash(f'Case {case_file_no} saved as draft.', 'info')
                else:
                    flash(f'Case {case_file_no} submitted!', 'success')
                return redirect(url_for('program_dashboard'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error: {e}', 'danger')
                return render_template('program_report_form.html', report_types=REPORT_TYPES, targets_list=TARGETS_ACHIEVED_LIST, psr_templates=PSR_TEMPLATES, dynamic_templates=PSR_DYNAMIC_TEMPLATES)

        # PROGRAM REPORTS
        meta = get_psr_meta(report_type)
        default_title = f"{meta['title']} Report"
        title = request.form.get('title') or default_title
        objective = request.form.get('objective') or "N/A"
        status_details = request.form.get('status_details') or "Specialized data submitted."
        ds_str = request.form.get('date_started')
        date_started = datetime.strptime(ds_str, '%Y-%m-%d').date() if ds_str else datetime.utcnow().date()

        new_report = ProgramReport(
            user_id=current_user.id, report_type=report_type, title=title, objective=objective,
            period_covered=request.form.get('period_covered', 'N/A'), date_started=date_started,
            previous_status_percentage=int(request.form.get('previous_status_percentage', 0)),
            status_percentage=int(request.form.get('status_percentage', 0)), status_details=status_details,
            constraints_requirements=request.form.get('constraints', 'None'), status="draft" if is_draft else "submitted"
        )

        try:
            db.session.add(new_report)
            db.session.flush() 

            if template_slug == "targets_achieved":
                target_selection = request.form.get("target_select")
                final_target = request.form.get("target_description_manual") if target_selection == "Other" else target_selection
                db.session.add(TargetsAchievedReport(id=new_report.id, target_description=final_target or "N/A", achievement_value=int(request.form.get("achievement_value", 0)), target_remarks=request.form.get("target_remarks", "None")))

            elif template_slug == "enforcement_operations":
                def safe_date(field):
                    v = request.form.get(field)
                    return datetime.strptime(v, "%Y-%m-%d").date() if v else None
                db.session.add(EnforcementOperation(program_report_id=new_report.id, sector_classification=request.form.get("seizure_sector"), date_commenced=safe_date("seizure_commenced"), date_completed=safe_date("seizure_completed"), location_address=request.form.get("seizure_location"), item_description_qty=request.form.get("seizure_item_desc"), total_value=request.form.get("seizure_value"), action_taken=request.form.get("seizure_action"), remarks=request.form.get("seizure_remarks")))

            elif template_slug in PSR_DYNAMIC_TEMPLATES:
                template_config = PSR_DYNAMIC_TEMPLATES[template_slug]
                fields = template_config["fields"]
                rows_data = {}
                for field in fields:
                    key = field["key"]
                    values = request.form.getlist(key)
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
                        db.session.add(PSRFieldValue(row_id=new_row.id, field_key=field["key"], field_value=value))

            db.session.commit()
            if is_draft:
                flash("Report saved as draft.", "info")
            else:
                flash("Report submitted successfully!", "success")
            return redirect(url_for('program_dashboard'))

        except Exception as e:
            db.session.rollback()
            print(f"DEBUG ERROR: {e}")
            flash(f"Submission Error: {e}", 'danger')
            return render_template('program_report_form.html', report_types=REPORT_TYPES, targets_list=TARGETS_ACHIEVED_LIST, psr_templates=PSR_TEMPLATES, dynamic_templates=PSR_DYNAMIC_TEMPLATES)

    return render_template('program_report_form.html', report_types=REPORT_TYPES, targets_list=TARGETS_ACHIEVED_LIST, psr_templates=PSR_TEMPLATES, dynamic_templates=PSR_DYNAMIC_TEMPLATES)

# ========================================================================
# UNIFIED PROGRAM DASHBOARD - PSR + COMPLAINTS COMBINED STATS
# ========================================================================
@app.route('/psr/dashboard')
@login_required
def program_dashboard():
    template_filter = request.args.get("template")
    search = request.args.get("search")

    # FETCH PSR REPORTS
    psr_query = ProgramReport.query
    if current_user.is_admin() or current_user.is_director() or current_user.is_evc():
        pass  
    elif current_user.is_supervisor():
        psr_query = psr_query.join(User).filter(User.fccpc_office == current_user.fccpc_office)
    else:
        psr_query = psr_query.filter(ProgramReport.user_id == current_user.id)
    
    # Apply template filter to PSR
    if template_filter:
        psr_query = psr_query.filter(ProgramReport.report_type == template_filter)
    if search:
        psr_query = psr_query.filter(ProgramReport.title.ilike(f"%{search}%"))
    
    psr_reports = psr_query.order_by(ProgramReport.date_created.desc()).all()
    
    # FETCH COMPLAINTS
    complaints_query = ConsumerComplaint.query
    if current_user.is_admin() or current_user.is_director() or current_user.is_evc():
        complaints = complaints_query.order_by(ConsumerComplaint.date_received.desc()).all()
    elif current_user.is_supervisor():
        complaints = complaints_query.join(User).filter(User.fccpc_office == current_user.fccpc_office).order_by(ConsumerComplaint.date_received.desc()).all()
    else:
        complaints = complaints_query.filter(ConsumerComplaint.user_id == current_user.id).order_by(ConsumerComplaint.date_received.desc()).all()

    # FILTER COMPLAINTS BY TEMPLATE (NEW!)
    if template_filter:
        # Only include complaints that match the selected template
        filtered_complaints = []
        for complaint in complaints:
            complaint_slug = None
            if complaint.status.upper() == 'RECEIVED':
                complaint_slug = 'complaints_received'
            elif complaint.status.upper() == 'ONGOING':
                complaint_slug = 'complaints_ongoing'
            elif complaint.status.upper() == 'RESOLVED':
                complaint_slug = 'complaints_resolved'
            
            # Only add if it matches the filter
            if complaint_slug == template_filter:
                filtered_complaints.append(complaint)
        
        complaints = filtered_complaints

    # COMBINE PSR + COMPLAINTS FOR UNIFIED VIEW
    # Add PSR metadata
    for report in psr_reports:
        report.psr_meta = get_psr_meta(report.report_type)
        report.is_complaint = False
    
    # Add Complaints as "reports" with metadata
    for complaint in complaints:
        # Map complaint status to template
        if complaint.status.upper() == 'RECEIVED':
            slug = 'complaints_received'
            code = 'PSR_03'
            title = 'DATABASE ON CONSUMER COMPLAINTS RECEIVED'
        elif complaint.status.upper() == 'ONGOING':
            slug = 'complaints_ongoing'
            code = 'PSR_04'
            title = 'DATABASE FOR ONGOING CONSUMER COMPLAINTS'
        elif complaint.status.upper() == 'RESOLVED':
            slug = 'complaints_resolved'
            code = 'PSR_05'
            title = 'DATABASE ON COMPLAINTS RESOLVED'
        else:
            slug = 'complaints_received'
            code = 'PSR_03'
            title = 'DATABASE ON CONSUMER COMPLAINTS RECEIVED'
        
        complaint.psr_meta = {
            'title': title,
            'code': code,
            'slug': slug,
            'category': 'complaints'
        }
        complaint.title = f"Case {complaint.case_file_no}"
        complaint.period_covered = f"Filed: {complaint.date_received.strftime('%Y-%m-%d')}"
        complaint.is_complaint = True
    
    # APPLY SEARCH FILTER TO COMPLAINTS (NEW!)
    if search:
        complaints = [c for c in complaints if search.lower() in c.title.lower() or 
                      search.lower() in c.case_file_no.lower()]
    
    # COMBINE ALL REPORTS
    all_reports = psr_reports + complaints
    all_reports.sort(key=lambda x: x.date_created if hasattr(x, 'date_created') else x.date_received, reverse=True)

    # CALCULATE UNIFIED STATS
    from datetime import timedelta
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)
    seven_days_ago = now - timedelta(days=7)
    
    # PSR stats (use original queries without filters for accurate totals)
    psr_total_query = ProgramReport.query
    if current_user.is_admin() or current_user.is_director() or current_user.is_evc():
        pass
    elif current_user.is_supervisor():
        psr_total_query = psr_total_query.join(User).filter(User.fccpc_office == current_user.fccpc_office)
    else:
        psr_total_query = psr_total_query.filter(ProgramReport.user_id == current_user.id)
    
    all_psr = psr_total_query.all()
    psr_total = len(all_psr)
    psr_month = len([r for r in all_psr if r.date_created >= thirty_days_ago])
    psr_week = len([r for r in all_psr if r.date_created >= seven_days_ago])
    psr_user = len([r for r in all_psr if r.user_id == current_user.id])
    
    # Complaint stats (use original queries without filters)
    complaints_total_query = ConsumerComplaint.query
    if current_user.is_admin() or current_user.is_director() or current_user.is_evc():
        all_complaints = complaints_total_query.all()
    elif current_user.is_supervisor():
        all_complaints = complaints_total_query.join(User).filter(User.fccpc_office == current_user.fccpc_office).all()
    else:
        all_complaints = complaints_total_query.filter(ConsumerComplaint.user_id == current_user.id).all()
    
    complaints_total = len(all_complaints)
    complaints_month = len([c for c in all_complaints if c.date_created >= thirty_days_ago])
    complaints_week = len([c for c in all_complaints if c.date_created >= seven_days_ago])
    complaints_user = len([c for c in all_complaints if c.user_id == current_user.id])
    
    # UNIFIED STATS (PSR + Complaints combined)
    stats = {
        'total': psr_total + complaints_total,
        'this_month': psr_month + complaints_month,
        'this_week': psr_week + complaints_week,
        'user_reports': psr_user + complaints_user
    }

    return render_template(
        "program_dashboard.html",
        reports=all_reports,
        templates=PSR_TEMPLATES,
        stats=stats,
        view_title="Program Status Reports"
    )


# REDIRECT OLD COMPLAINTS DASHBOARD
@app.route('/complaints_dashboard')
@login_required
def complaints_dashboard():
    flash("Complaints are now integrated into the main PSR dashboard!", "info")
    return redirect(url_for('program_dashboard'))

# ========================================================================
# VIEW ROUTES - HANDLE BOTH PSR AND COMPLAINT VIEWS
# ========================================================================
@app.route('/psr/view/<int:report_id>')
@login_required
def view_program_report(report_id):
    # Check if this is a complaint or PSR based on URL parameter
    is_complaint = request.args.get('type') == 'complaint'
    
    if is_complaint:
        # It's a complaint - query ConsumerComplaint table
        complaint = ConsumerComplaint.query.get(report_id)
        
        if not complaint:
            flash('Complaint not found.', 'danger')
            return redirect(url_for('program_dashboard'))
        
        if not current_user.is_admin() and complaint.user_id != current_user.id:
            flash('You are not authorized to view this complaint.', 'danger')
            return redirect(url_for('program_dashboard'))
        
        # Determine which complaint view template to use
        if complaint.status.upper() == 'RECEIVED':
            template = 'psr_views/complaints_received.html'
        elif complaint.status.upper() == 'ONGOING':
            template = 'psr_views/complaints_ongoing.html'
        elif complaint.status.upper() == 'RESOLVED':
            template = 'psr_views/complaints_resolved.html'
        else:
            template = 'psr_views/complaints_received.html'
        
        return render_template(template, report=complaint)
    
    else:
        # It's a PSR report - query ProgramReport table
        report = ProgramReport.query.get(report_id)
        
        if not report:
            flash('Report not found.', 'danger')
            return redirect(url_for('program_dashboard'))
        
        if not current_user.is_admin() and report.user_id != current_user.id:
            flash('You are not authorized to view this report.', 'danger')
            return redirect(url_for('program_dashboard'))
        
        template_slug = report.report_type
        if template_slug in PSR_DYNAMIC_TEMPLATES:
            config = PSR_DYNAMIC_TEMPLATES[template_slug]
            rows = []
            for row in report.psr_rows:
                row_data = {}
                for value in row.values:
                    row_data[value.field_key] = value.field_value
                rows.append(row_data)
            return render_template("psr_views/dynamic.html", report=report, config=config, rows=rows)
        return render_template(f"psr_views/{template_slug}.html", report=report)

@app.route('/psr/delete/<int:report_id>', methods=['POST'])
@login_required
def delete_program_report(report_id):
    # Check if this is a complaint or PSR based on URL parameter
    is_complaint = request.args.get('type') == 'complaint'
    
    if is_complaint:
        # It's a complaint - query ConsumerComplaint table
        complaint = ConsumerComplaint.query.get(report_id)
        
        if not complaint:
            flash("Complaint not found.", "danger")
            return redirect(url_for('program_dashboard'))
        
        if not current_user.is_admin() and complaint.user_id != current_user.id:
            flash("You are not authorized to delete this complaint.", "danger")
            return redirect(url_for('program_dashboard'))
        
        try:
            db.session.delete(complaint)
            db.session.commit()
            flash("Complaint deleted successfully.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Delete failed: {e}", "danger")
    
    else:
        # It's a PSR report - query ProgramReport table
        report = ProgramReport.query.get(report_id)
        
        if not report:
            flash("Report not found.", "danger")
            return redirect(url_for('program_dashboard'))
        
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

# EXPORT ROUTES

@app.route('/psr/export_csv')
@login_required
def export_psr_data():
    if current_user.is_admin():
        reports = ProgramReport.query.order_by(ProgramReport.date_created.desc()).all()
    else:
        reports = ProgramReport.query.filter_by(user_id=current_user.id).order_by(ProgramReport.date_created.desc()).all()
    csv_data = "ID,Report Type,Title,Period Covered,Objective,Status Details,Achievement (%),Date Created,Agent Name\n"
    for report in reports:
        details = report.status_details.replace('\n', ' ').replace(',', ';') 
        row = f"{report.id},"
        row += f"{report.report_type},"
        row += f"\"{report.title}\","
        row += f"{report.period_covered},"
        row += f"{report.objective},"
        row += f"\"{details}\","
        row += f"{report.status_percentage},"
        row += f"{report.date_created.strftime('%Y-%m-%d %H:%M')},"
        row += f"{report.agent.name}\n"
        csv_data += row
    from io import BytesIO
    buffer = BytesIO()
    buffer.write(csv_data.encode('utf-8'))
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name='PSR_Export.csv', mimetype='text/csv')

@app.route("/psr/export/<int:report_id>")
@login_required
def export_single_psr(report_id):
    report = ProgramReport.query.get_or_404(report_id)
    if not current_user.is_admin() and report.user_id != current_user.id:
        abort(403)
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
    writer.writerow([f["label"] for f in fields])
    for row in report.psr_rows:
        row_dict = {v.field_key: v.field_value for v in row.values}
        writer.writerow([row_dict.get(f["key"], "") for f in fields])
    output.seek(0)
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename=psr_{report.id}.csv"})

@app.route("/admin/audit-logs")
@admin_required
def audit_logs():
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(500).all()
    return render_template("audit_logs.html", logs=logs)

@app.route('/admin/toggle-user/<int:user_id>', methods=['POST'])
@admin_required
def toggle_user_status(user_id):
    user = User.query.get_or_404(user_id)
    user.is_enabled = not user.is_enabled
    db.session.commit()
    log_action(action="User Status Changed", target_user=user, details=f"Account {'re-activated' if user.is_enabled else 'suspended'}")
    flash(f"User {'re-activated' if user.is_enabled else 'suspended'} successfully.", "success")
    return redirect(url_for('admin_dashboard'))

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500
    
if __name__ == '__main__':
    app.run(debug=True)
