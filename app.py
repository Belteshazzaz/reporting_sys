# app.py - PHASE 1 UPDATES
# CHANGES:
# 1. Added date_ended field to ProgramReport model
# 2. Added complaints analytics route with counts
# 3. Updated submission logic to capture date_ended

from datetime import datetime, timedelta
import json, os
import pandas as pd
import plotly.graph_objects as go
import plotly.utils
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask import Flask, render_template, request, redirect, url_for, flash, abort, Response, send_file
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
from io import StringIO, BytesIO
import csv
from collections import Counter

# Load environment variables
load_dotenv()

# Nigerian States List
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

# Flask App Configuration
app = Flask(__name__)

# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'sqlite:///project.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

# Security Headers
@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

# Database Initialization
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Rate Limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# ==================== DATABASE MODELS ====================

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
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
        return f'<PriceReport {self.id}: {self.product_name}>'

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
    date_ended = db.Column(db.Date, nullable=True)  # ✅ NEW FIELD - PHASE 1
    previous_status_percentage = db.Column(db.Integer, default=0)
    status_details = db.Column(db.Text, nullable=True)
    constraints_requirements = db.Column(db.Text)
    status_percentage = db.Column(db.Integer, default=0)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    agent = db.relationship('User', backref=db.backref('program_reports', lazy=True))
    targets_report = db.relationship('TargetsAchievedReport', uselist=False, backref='base_report')
    psr_rows = db.relationship("PSRRow", backref="program_report", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ProgramReport {self.id}: {self.title}>"

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
        return f'<Complaint {self.case_file_no}>'
    
    def get_respondent_name(self):
        """Extract respondent name from respondent_details"""
        try:
            lines = self.respondent_details.split('\n')
            for line in lines:
                if line.startswith('Name:'):
                    return line.replace('Name:', '').strip()
            return "Unknown"
        except:
            return "Unknown"

class TargetsAchievedReport(db.Model):
    __tablename__ = 'targets_achieved_reports'
    id = db.Column(db.Integer, db.ForeignKey('program_reports.id'), primary_key=True) 
    target_description = db.Column(db.Text, nullable=False)
    achievement_value = db.Column(db.Integer, default=0)
    target_remarks = db.Column(db.Text)
    
    def __repr__(self):
        return f"<TargetsAchievedReport {self.id}>"

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
        return f"<AuditLog {self.action}>"

# ==================== LOGIN MANAGER ====================

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' 
login_manager.login_message = 'Please log in to access this page.' 

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==================== HELPER FUNCTIONS ====================

def create_price_trend_chart(reports):
    """Generate price trend chart for price reports"""
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

def log_action(action, target_user=None, details=None):
    """Log user actions to audit trail"""
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
    except Exception:
        db.session.rollback()

# ==================== DECORATORS ====================

def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('Access denied: Administrator privileges required.', 'danger')
            return redirect(url_for('program_dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def supervisor_required(f):
    """Decorator to require supervisor access"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_supervisor():
            flash("Supervisor access required.", "danger")
            return redirect(url_for("program_dashboard"))
        return f(*args, **kwargs)
    return decorated

# ==================== AUTHENTICATION ROUTES ====================

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration - restricted after first user"""
    if User.query.count() > 0 and not current_user.is_authenticated:
        flash('Registration is currently restricted. Please contact an Administrator.', 'warning')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        name = request.form.get('name', '').strip()
        sex = request.form.get('sex', '').strip()
        fccpc_office = request.form.get('fccpc_office', '').strip()
        
        if not all([email, password, name, sex, fccpc_office]):
            flash('All fields are required!', 'danger')
            return redirect(url_for('register'))
        
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
        
        # First user becomes admin
        if User.query.count() == 0:
            new_user.role = 9
            flash('Initial Admin account created! Please log in.', 'success')
        else:
            flash('Agent account created! You can now log in.', 'success')
        
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    
    return render_template('register.html', states=NIGERIAN_STATES)

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    """User login with rate limiting"""
    if current_user.is_authenticated:
        return redirect(url_for('program_dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
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
@login_required
def logout():
    """User logout"""
    log_action(action="Logout", details=f"{current_user.email} logged out")
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# ==================== ADMIN ROUTES ====================

@app.route('/admin')
@admin_required
def admin_dashboard():
    """Admin dashboard for user management"""
    role = request.args.get("role")
    search = request.args.get("search")
    
    query = User.query
    if role:
        try:
            query = query.filter(User.role == int(role))
        except ValueError:
            pass
    if search:
        query = query.filter(User.name.ilike(f"%{search}%") | User.email.ilike(f"%{search}%"))
    
    users = query.order_by(User.id.desc()).all()
    return render_template("admin_dashboard.html", users=users)

@app.route('/admin/change-password/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def change_password(user_id):
    """Admin can change any user's password"""
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        # If admin is changing their own password, require old password
        if user.id == current_user.id:
            old_password = request.form.get('old_password', '').strip()
            
            if not old_password:
                flash('Current password is required.', 'danger')
                return render_template('change_password.html', user=user, is_self=True)
            
            if not user.check_password(old_password):
                flash('Current password is incorrect.', 'danger')
                return render_template('change_password.html', user=user, is_self=True)
        
        # Get new password
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        # Validation
        if not new_password:
            flash('New password is required.', 'danger')
            return render_template('change_password.html', user=user, is_self=(user.id == current_user.id))
        
        if len(new_password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return render_template('change_password.html', user=user, is_self=(user.id == current_user.id))
        
        if new_password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('change_password.html', user=user, is_self=(user.id == current_user.id))
        
        # Change password
        user.set_password(new_password)
        
        try:
            db.session.commit()
            
            # Log the action
            if user.id == current_user.id:
                log_action(
                    action="Password Changed",
                    target_user=user,
                    details="Admin changed their own password"
                )
                flash('Your password has been changed successfully!', 'success')
            else:
                log_action(
                    action="Password Changed",
                    target_user=user,
                    details=f"Admin changed password for {user.email}"
                )
                flash(f'Password for {user.name} has been changed successfully!', 'success')
            
            return redirect(url_for('admin_dashboard'))
        except Exception:
            db.session.rollback()
            flash('An error occurred while changing the password.', 'danger')
    
    return render_template('change_password.html', user=user, is_self=(user.id == current_user.id))


@app.route('/admin/reset/<int:user_id>', methods=['POST'])
@admin_required
def reset_password(user_id):
    """Reset user password"""
    user = User.query.get_or_404(user_id)
    
    characters = string.ascii_letters + string.digits
    temp_password = ''.join(secrets.choice(characters) for i in range(12))
    
    user.set_password(temp_password)
    db.session.commit()
    
    log_action(action="Password Reset", target_user=user, details=f"Admin reset password for {user.email}")
    flash(f"Password for {user.name} ({user.email}) has been reset. New Temporary Password: {temp_password}", 'warning')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/elevate_user/<int:user_id>/<int:new_role>')
@admin_required
def elevate_user(user_id, new_role):
    """Change user role"""
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash("You cannot change your own role.", "danger")
        return redirect(url_for("admin_dashboard"))
    
    if new_role not in [1, 2, 3, 4, 9]:
        flash("Invalid role selected.", "danger")
        return redirect(url_for("admin_dashboard"))
    
    old_role = user.role
    user.role = new_role
    
    try:
        db.session.commit()
        log_action(action="Role Changed", target_user=user, details=f"Role changed from {old_role} to {new_role}")
        flash(f"{user.name} role updated successfully.", "success")
    except Exception:
        db.session.rollback()
        flash("Role update failed.", "danger")
    
    return redirect(url_for("admin_dashboard"))

@app.route('/admin/toggle-user/<int:user_id>', methods=['POST'])
@admin_required
def toggle_user_status(user_id):
    """Enable/disable user account"""
    user = User.query.get_or_404(user_id)
    user.is_enabled = not user.is_enabled
    db.session.commit()
    
    log_action(
        action="User Status Changed",
        target_user=user,
        details=f"Account {'re-activated' if user.is_enabled else 'suspended'}"
    )
    flash(f"User {'re-activated' if user.is_enabled else 'suspended'} successfully.", "success")
    
    return redirect(url_for('admin_dashboard'))

@app.route("/admin/audit-logs")
@admin_required
def audit_logs():
    """View audit logs"""
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(500).all()
    return render_template("audit_logs.html", logs=logs)

# ==================== PRICE REPORTS ROUTES ====================

@app.route('/', methods=['GET'])
@login_required
def dashboard():
    """Price reports dashboard"""
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
    
    return render_template(
        'dashboard.html',
        data=reports,
        view_title=view_title,
        price_trend_chart_json=price_trend_chart_json,
        request=request
    )

@app.route('/report')
@login_required
def report_form():
    """Price report submission form"""
    return render_template('report_form.html')

@app.route('/submit', methods=['POST'])
@login_required
def submit_report():
    """Submit price report"""
    if request.method == 'POST':
        try:
            agent_name = current_user.name
            product_name = request.form.get('product_name', '').strip()
            market_location = request.form.get('market_location', '').strip()
            price = float(request.form.get('price', 0))
            unit = request.form.get('unit', '').strip()
            
            new_report = PriceReport(
                agent_name=agent_name,
                product_name=product_name,
                market_location=market_location,
                price=price,
                unit=unit,
                user_id=current_user.id
            )
            
            db.session.add(new_report)
            db.session.commit()
            flash(f'Report for "{product_name}" saved successfully!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            flash("There was an issue submitting your report.", 'danger')
            return redirect(url_for('report_form'))
    
    return redirect(url_for('report_form'))

@app.route('/delete/<int:report_id>', methods=['POST'])
@admin_required
def delete_report(report_id):
    """Delete price report"""
    report_to_delete = PriceReport.query.get_or_404(report_id)
    
    try:
        product_name = report_to_delete.product_name
        db.session.delete(report_to_delete)
        db.session.commit()
        
        log_action(
            action="Price Report Deleted",
            details=f"Deleted report ID {report_id} ({product_name})"
        )
        flash(f'Report ID {report_id} ({product_name}) deleted successfully.', 'danger')
    except Exception:
        db.session.rollback()
        flash('An error occurred during report deletion.', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/edit/<int:report_id>', methods=['GET', 'POST'])
@admin_required
def edit_report(report_id):
    """Edit price report"""
    report = PriceReport.query.get_or_404(report_id)
    
    if request.method == 'POST':
        try:
            report.product_name = request.form.get('product_name', '').strip()
            report.market_location = request.form.get('market_location', '').strip()
            report.price = float(request.form.get('price', 0))
            report.unit = request.form.get('unit', '').strip()
            
            db.session.commit()
            flash(f'Report ID {report_id} updated successfully!', 'success')
            return redirect(url_for('dashboard'))
        except Exception:
            db.session.rollback()
            flash('An error occurred while updating the report.', 'danger')
    
    return render_template(
        'report_form.html',
        report=report,
        states=NIGERIAN_STATES,
        form_title=f"Edit Report ID {report_id} by {report.agent_name}"
    )

# ==================== PSR REPORT SUBMISSION ====================

@app.route('/psr/submit', methods=['GET', 'POST'])
@login_required 
def program_report_form():
    """Program status report submission form"""
    if request.method == 'POST':
        try:
            action = request.form.get("action", "submit")
            is_draft = action == "draft"
            template_slug = report_type = request.form.get("report_type")

            if not template_slug:
                flash("No report template selected.", "danger")
                return render_template(
                    "program_report_form.html",
                    report_types=REPORT_TYPES,
                    targets_list=TARGETS_ACHIEVED_LIST,
                    psr_templates=PSR_TEMPLATES
                )

            # COMPLAINT TEMPLATES
            if template_slug.startswith("complaints_"):
                case_file_no = request.form.get('case_file_no', '').strip()
                
                if not case_file_no:
                    flash('Case File No. is required.', 'danger')
                    return render_template(
                        'program_report_form.html',
                        report_types=REPORT_TYPES,
                        targets_list=TARGETS_ACHIEVED_LIST,
                        psr_templates=PSR_TEMPLATES
                    )
                
                if ConsumerComplaint.query.filter_by(case_file_no=case_file_no).first():
                    flash(f'Error: Case File No. {case_file_no} already exists.', 'danger')
                    return render_template(
                        'program_report_form.html',
                        report_types=REPORT_TYPES,
                        targets_list=TARGETS_ACHIEVED_LIST,
                        psr_templates=PSR_TEMPLATES,
                        dynamic_templates=PSR_DYNAMIC_TEMPLATES
                    )

                # Build complainant details
                c_name = request.form.get('complainant_name', '')
                c_addr = request.form.get('complainant_address', '')
                c_email = request.form.get('complainant_email', '')
                c_phone = request.form.get('complainant_phone', '')
                complainant_details = f"Name: {c_name}\nAddress: {c_addr}\nEmail: {c_email}\nPhone: {c_phone}"
                
                # Build respondent details
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

                db.session.add(new_complaint)
                db.session.commit()
                
                if is_draft:
                    flash(f'Case {case_file_no} saved as draft.', 'info')
                else:
                    flash(f'Case {case_file_no} submitted!', 'success')
                
                return redirect(url_for('program_dashboard'))

            # PROGRAM REPORTS
            meta = get_psr_meta(report_type)
            default_title = f"{meta['title']} Report"
            title = request.form.get('title') or default_title
            objective = request.form.get('objective') or "N/A"
            status_details = request.form.get('status_details') or "Specialized data submitted."
            
            # ✅ PHASE 1: Capture date_started and date_ended
            ds_str = request.form.get('date_started')
            date_started = datetime.strptime(ds_str, '%Y-%m-%d').date() if ds_str else datetime.utcnow().date()
            
            de_str = request.form.get('date_ended')  # ✅ NEW: Date Ended field
            date_ended = datetime.strptime(de_str, '%Y-%m-%d').date() if de_str else None

            new_report = ProgramReport(
                user_id=current_user.id,
                report_type=report_type,
                title=title,
                objective=objective,
                period_covered=request.form.get('period_covered', 'N/A'),
                date_started=date_started,
                date_ended=date_ended,  # ✅ NEW: Save date_ended
                previous_status_percentage=int(request.form.get('previous_status_percentage', 0)),
                status_percentage=int(request.form.get('status_percentage', 0)),
                status_details=status_details,
                constraints_requirements=request.form.get('constraints', 'None'),
                status="draft" if is_draft else "submitted"
            )

            db.session.add(new_report)
            db.session.flush() 

            if template_slug == "targets_achieved":
                target_selection = request.form.get("target_select")
                final_target = request.form.get("target_description_manual") if target_selection == "Other" else target_selection
                
                db.session.add(TargetsAchievedReport(
                    id=new_report.id,
                    target_description=final_target or "N/A",
                    achievement_value=int(request.form.get("achievement_value", 0)),
                    target_remarks=request.form.get("target_remarks", "None")
                ))

            elif template_slug == "enforcement_operations":
                def safe_date(field):
                    v = request.form.get(field)
                    return datetime.strptime(v, "%Y-%m-%d").date() if v else None
                
                db.session.add(EnforcementOperation(
                    program_report_id=new_report.id,
                    sector_classification=request.form.get("seizure_sector"),
                    date_commenced=safe_date("seizure_commenced"),
                    date_completed=safe_date("seizure_completed"),
                    location_address=request.form.get("seizure_location"),
                    item_description_qty=request.form.get("seizure_item_desc"),
                    total_value=request.form.get("seizure_value"),
                    action_taken=request.form.get("seizure_action"),
                    remarks=request.form.get("seizure_remarks")
                ))

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
                        db.session.add(PSRFieldValue(
                            row_id=new_row.id,
                            field_key=field["key"],
                            field_value=value
                        ))

            db.session.commit()
            
            if is_draft:
                flash("Report saved as draft.", "info")
            else:
                flash("Report submitted successfully!", "success")
            
            return redirect(url_for('program_dashboard'))

        except Exception as e:
            db.session.rollback()
            flash(f"Submission Error: {str(e)}", 'danger')
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

# ==================== UNIFIED PROGRAM DASHBOARD ====================

@app.route('/psr/dashboard')
@login_required
def program_dashboard():
    """Unified dashboard - PSR + Complaints combined"""
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

    # FILTER COMPLAINTS BY TEMPLATE
    if template_filter:
        filtered_complaints = []
        for complaint in complaints:
            complaint_slug = None
            if complaint.status.upper() == 'RECEIVED':
                complaint_slug = 'complaints_received'
            elif complaint.status.upper() == 'ONGOING':
                complaint_slug = 'complaints_ongoing'
            elif complaint.status.upper() == 'RESOLVED':
                complaint_slug = 'complaints_resolved'
            
            if complaint_slug == template_filter:
                filtered_complaints.append(complaint)
        
        complaints = filtered_complaints

    # Add PSR metadata
    for report in psr_reports:
        report.psr_meta = get_psr_meta(report.report_type)
        report.is_complaint = False
    
    # Add Complaints metadata
    for complaint in complaints:
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
    
    # APPLY SEARCH FILTER TO COMPLAINTS
    if search:
        complaints = [c for c in complaints if search.lower() in c.title.lower() or 
                      search.lower() in c.case_file_no.lower()]
    
    # COMBINE ALL REPORTS
    all_reports = psr_reports + complaints
    all_reports.sort(key=lambda x: x.date_created if hasattr(x, 'date_created') else x.date_received, reverse=True)

    # ✅ PHASE 1: Add result count for filtered/searched results
    result_count = len(all_reports)

    # CALCULATE UNIFIED STATS (without filters for accurate totals)
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)
    seven_days_ago = now - timedelta(days=7)
    
    # PSR stats
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
    
    # Complaint stats
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
    
    # UNIFIED STATS
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
        result_count=result_count,  # ✅ PHASE 1: Pass result count to template
        view_title="Program Status Reports"
    )

# ✅ PHASE 1: NEW ROUTE - Complaints Analytics
@app.route('/psr/analytics/complaints')
@login_required
def complaints_analytics():
    """Analytics dashboard for consumer complaints with counts"""
    
    # Fetch all accessible complaints
    if current_user.is_admin() or current_user.is_director() or current_user.is_evc():
        complaints = ConsumerComplaint.query.all()
    elif current_user.is_supervisor():
        complaints = ConsumerComplaint.query.join(User).filter(User.fccpc_office == current_user.fccpc_office).all()
    else:
        complaints = ConsumerComplaint.query.filter_by(user_id=current_user.id).all()
    
    # Count by respondent (company/organization)
    respondent_counts = Counter()
    for complaint in complaints:
        respondent = complaint.get_respondent_name()
        respondent_counts[respondent] += 1
    
    # Get top 15 most complained companies
    top_respondents = respondent_counts.most_common(15)
    
    # Count by status
    status_counts = Counter([c.status for c in complaints])
    
    # Count by sector
    sector_counts = Counter()
    for complaint in complaints:
        sector = complaint.sector_category or "Unknown"
        sector_counts[sector] += 1
    
    # Monthly trend (last 12 months)
    monthly_counts = {}
    now = datetime.utcnow()
    for i in range(12):
        month_date = now - timedelta(days=30*i)
        month_key = month_date.strftime('%Y-%m')
        monthly_counts[month_key] = 0
    
    for complaint in complaints:
        month_key = complaint.date_received.strftime('%Y-%m')
        if month_key in monthly_counts:
            monthly_counts[month_key] += 1
    
    # Create charts
    # Chart 1: Top Companies by Complaint Count
    if top_respondents:
        companies_chart = go.Figure(data=[
            go.Bar(
                x=[count for _, count in top_respondents],
                y=[name for name, _ in top_respondents],
                orientation='h',
                marker=dict(color='#DC3545')
            )
        ])
        companies_chart.update_layout(
            title='Top 15 Companies by Complaint Count',
            xaxis_title='Number of Complaints',
            yaxis_title='Company/Organization',
            height=500,
            margin=dict(l=20, r=20, t=60, b=20)
        )
        companies_chart_json = json.dumps(companies_chart, cls=plotly.utils.PlotlyJSONEncoder)
    else:
        companies_chart_json = None
    
    # Chart 2: Complaints by Status
    status_chart = go.Figure(data=[
        go.Pie(
            labels=list(status_counts.keys()),
            values=list(status_counts.values()),
            marker=dict(colors=['#28A745', '#FFC107', '#DC3545'])
        )
    ])
    status_chart.update_layout(
        title='Complaints by Status',
        height=400
    )
    status_chart_json = json.dumps(status_chart, cls=plotly.utils.PlotlyJSONEncoder)
    
    # Chart 3: Monthly Trend
    sorted_months = sorted(monthly_counts.keys())
    month_chart = go.Figure(data=[
        go.Scatter(
            x=sorted_months,
            y=[monthly_counts[m] for m in sorted_months],
            mode='lines+markers',
            line=dict(color='#007BFF', width=3),
            marker=dict(size=8)
        )
    ])
    month_chart.update_layout(
        title='Complaint Trend (Last 12 Months)',
        xaxis_title='Month',
        yaxis_title='Number of Complaints',
        height=400,
        margin=dict(l=20, r=20, t=60, b=20)
    )
    month_chart_json = json.dumps(month_chart, cls=plotly.utils.PlotlyJSONEncoder)
    
    # Prepare analytics data
    analytics_data = {
        'total_complaints': len(complaints),
        'top_respondents': top_respondents,
        'status_counts': dict(status_counts),
        'sector_counts': dict(sector_counts.most_common(10)),
        'companies_chart': companies_chart_json,
        'status_chart': status_chart_json,
        'month_chart': month_chart_json
    }
    
    return render_template(
        'complaints_analytics.html',
        analytics=analytics_data
    )

# ✅ PHASE 1: Export Complaints Analytics to Excel
@app.route('/psr/analytics/complaints/export')
@login_required
def export_complaints_analytics():
    """Export complaints analytics to Excel"""
    
    # Fetch complaints (same access control as analytics page)
    if current_user.is_admin() or current_user.is_director() or current_user.is_evc():
        complaints = ConsumerComplaint.query.all()
    elif current_user.is_supervisor():
        complaints = ConsumerComplaint.query.join(User).filter(User.fccpc_office == current_user.fccpc_office).all()
    else:
        complaints = ConsumerComplaint.query.filter_by(user_id=current_user.id).all()
    
    # Count by respondent
    respondent_counts = Counter()
    for complaint in complaints:
        respondent = complaint.get_respondent_name()
        respondent_counts[respondent] += 1
    
    # Create CSV
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['Rank', 'Company/Organization', 'Number of Complaints'])
    
    # Data
    for rank, (respondent, count) in enumerate(respondent_counts.most_common(), 1):
        writer.writerow([rank, respondent, count])
    
    output.seek(0)
    
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=complaints_analytics.csv"}
    )

# Redirect old complaints dashboard
@app.route('/complaints_dashboard')
@login_required
def complaints_dashboard():
    """Redirect old complaints dashboard to unified dashboard"""
    flash("Complaints are now integrated into the main PSR dashboard!", "info")
    return redirect(url_for('program_dashboard'))

# ==================== VIEW ROUTES ====================

@app.route('/psr/view/<int:report_id>')
@login_required
def view_program_report(report_id):
    """View PSR report or complaint"""
    is_complaint = request.args.get('type') == 'complaint'
    
    if is_complaint:
        complaint = ConsumerComplaint.query.get(report_id)
        
        if not complaint:
            flash('Complaint not found.', 'danger')
            return redirect(url_for('program_dashboard'))
        
        if not current_user.is_admin() and not current_user.is_supervisor() and complaint.user_id != current_user.id:
            flash('You are not authorized to view this complaint.', 'danger')
            return redirect(url_for('program_dashboard'))
        
        # Determine template
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
        report = ProgramReport.query.get(report_id)
        
        if not report:
            flash('Report not found.', 'danger')
            return redirect(url_for('program_dashboard'))
        
        if not current_user.is_admin() and not current_user.is_supervisor() and report.user_id != current_user.id:
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
    """Delete PSR report or complaint"""
    is_complaint = request.args.get('type') == 'complaint'
    
    if is_complaint:
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
        except Exception:
            db.session.rollback()
            flash("Delete failed.", "danger")
    
    else:
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
        except Exception:
            db.session.rollback()
            flash("Delete failed.", "danger")
    
    return redirect(url_for('program_dashboard'))

# ==================== EXPORT ROUTES ====================

@app.route('/psr/export_csv')
@login_required
def export_psr_data():
    """Export PSR reports to CSV"""
    if current_user.is_admin():
        reports = ProgramReport.query.order_by(ProgramReport.date_created.desc()).all()
    else:
        reports = ProgramReport.query.filter_by(user_id=current_user.id).order_by(ProgramReport.date_created.desc()).all()
    
    csv_data = "ID,Report Type,Title,Period Covered,Objective,Status Details,Achievement (%),Date Started,Date Ended,Date Created,Agent Name\n"
    
    for report in reports:
        details = report.status_details.replace('\n', ' ').replace(',', ';') if report.status_details else ''
        date_ended_str = report.date_ended.strftime('%Y-%m-%d') if report.date_ended else 'N/A'
        
        row = f"{report.id},"
        row += f"{report.report_type},"
        row += f'"{report.title}",'
        row += f"{report.period_covered},"
        row += f"{report.objective},"
        row += f'"{details}",'
        row += f"{report.status_percentage},"
        row += f"{report.date_started.strftime('%Y-%m-%d') if report.date_started else 'N/A'},"
        row += f"{date_ended_str},"
        row += f"{report.date_created.strftime('%Y-%m-%d %H:%M')},"
        row += f"{report.agent.name}\n"
        csv_data += row
    
    buffer = BytesIO()
    buffer.write(csv_data.encode('utf-8'))
    buffer.seek(0)
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name='PSR_Export.csv',
        mimetype='text/csv'
    )

@app.route("/psr/export/<int:report_id>")
@login_required
def export_single_psr(report_id):
    """Export single PSR report to CSV"""
    report = ProgramReport.query.get_or_404(report_id)
    
    if not current_user.is_admin() and report.user_id != current_user.id:
        abort(403)
    
    if report.report_type not in PSR_DYNAMIC_TEMPLATES:
        flash("Export only available for dynamic templates", "warning")
        return redirect(url_for("view_program_report", report_id=report.id))
    
    config = PSR_DYNAMIC_TEMPLATES[report.report_type]
    fields = config["fields"]
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([f["label"] for f in fields])
    
    for row in report.psr_rows:
        row_dict = {v.field_key: v.field_value for v in row.values}
        writer.writerow([row_dict.get(f["key"], "") for f in fields])
    
    output.seek(0)
    
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=psr_{report.id}.csv"}
    )

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(e):
    """404 error handler"""
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    """500 error handler"""
    return render_template('500.html'), 500

@app.errorhandler(403)
def forbidden(e):
    """403 error handler"""
    flash('Access denied.', 'danger')
    return redirect(url_for('program_dashboard'))

# ==================== APPLICATION ENTRY POINT ====================

if __name__ == '__main__':
    app.run(debug=True)
