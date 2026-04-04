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
from flask import Flask, render_template, request, redirect, url_for, flash, abort, Response, send_file, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
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
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from file_upload_utils import (
    save_file, delete_file, get_file_path,
    format_file_size, get_file_icon,
    UPLOAD_FOLDER, MAX_FILES_PER_REPORT,
    init_upload_folder
)

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

HQ_DEPARTMENTS = [
    'Mergers and Acquisitions',
    'Surveillance and Investigation',
    'Consumer and Business Education',
    'Quality Assurance Development',
    'Administration',
    'Finance and Accounts',
    'Planning Research and Statistics',
    'Legal Services',
    'Internal Audit',
    'Special Duties',
    'Anti-Competitive Practices',
    'Information Communication Technology',
    'Procurement',
    'Public Relations',
    'Corporate Affairs',
]

PSR_DEPT = 'Planning Research and Statistics'  # always sees everything

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

# MFA OTP expiry in minutes
OTP_EXPIRY_MINUTES = 10

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
    office_type = db.Column(db.String(20), default='zonal', nullable=False)   # 'hq' or 'zonal'
    department = db.Column(db.String(100), nullable=True)                      # HQ dept, None for zonal
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

    def is_hq(self):
        """True if user is based at HQ (Abuja)."""
        return self.office_type == 'HQ'

    def is_psr(self):
        """True if user belongs to Planning Research and Statistics department."""
        return self.department == 'Planning Research and Statistics'

    def can_view_all_reports(self):
        """Admins, PSR dept, and zonal/state users can view all reports."""
        return self.is_admin() or self.is_psr() or not self.is_hq()

    def can_submit_template(self, template_dept):
        """
        Returns True if this user is allowed to submit a report for a template
        that belongs to `template_dept` (None means unassigned = open to all).
        """
        if self.is_admin() or self.is_psr() or not self.is_hq():
            return True
        if template_dept is None:          # unassigned template — visible to all
            return True
        return self.department == template_dept

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
    date_ended = db.Column(db.Date, nullable=True)  # âœ… NEW FIELD - PHASE 1
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

# ── Custom Template Builder Models ──────────────────────────────

class CustomTemplate(db.Model):
    __tablename__ = 'custom_templates'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(255), nullable=False)
    code        = db.Column(db.String(20),  nullable=False)
    slug        = db.Column(db.String(100), nullable=False, unique=True)
    category    = db.Column(db.String(50),  default='custom')
    department  = db.Column(db.String(100), nullable=True)   # None = visible to all
    is_active   = db.Column(db.Boolean, default=True, nullable=False)
    created_by  = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    fields      = db.relationship('CustomTemplateField',
                                  backref='template',
                                  cascade='all, delete-orphan',
                                  order_by='CustomTemplateField.sort_order')
    creator     = db.relationship('User', backref=db.backref('custom_templates', lazy=True))

    def to_dynamic_config(self):
        """Return a config dict compatible with PSR_DYNAMIC_TEMPLATES format."""
        return {
            'title': self.name,
            'fields': [
                {
                    'key':      f.field_key,
                    'label':    f.label,
                    'type':     f.field_type,
                    'required': f.is_required,
                    'options':  json.loads(f.options) if f.options else [],
                }
                for f in self.fields
            ]
        }

    def __repr__(self):
        return f'<CustomTemplate {self.code}: {self.name}>'


class CustomTemplateField(db.Model):
    __tablename__ = 'custom_template_fields'
    id          = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey('custom_templates.id', ondelete='CASCADE'), nullable=False)
    field_key   = db.Column(db.String(100), nullable=False)
    label       = db.Column(db.String(255), nullable=False)
    field_type  = db.Column(db.String(50),  default='text', nullable=False)
    options     = db.Column(db.Text,  nullable=True)   # JSON array for dropdowns
    is_required = db.Column(db.Boolean, default=False)
    sort_order  = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f'<CustomTemplateField {self.field_key}>'

class ReportAttachment(db.Model):
    """
    Unified file attachments for both ProgramReports and ConsumerComplaints.
    Only one of report_id or complaint_id will be set per record.
    """
    __tablename__ = 'report_attachments'

    id = db.Column(db.Integer, primary_key=True)

    # One of these two will be set — the other will be NULL
    report_id = db.Column(db.Integer, db.ForeignKey('program_reports.id', ondelete='CASCADE'), nullable=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('consumer_complaints.id', ondelete='CASCADE'), nullable=True)

    filename = db.Column(db.String(255), nullable=False)           # Unique filename on disk
    original_filename = db.Column(db.String(255), nullable=False)  # Original user filename
    file_size = db.Column(db.Integer, nullable=False)              # Size in bytes
    file_type = db.Column(db.String(50), nullable=False)           # File extension
    upload_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    # Relationships
    report = db.relationship('ProgramReport', backref=db.backref('attachments', lazy=True, cascade='all, delete-orphan'))
    complaint = db.relationship('ConsumerComplaint', backref=db.backref('attachments', lazy=True, cascade='all, delete-orphan'))
    uploader = db.relationship('User', backref=db.backref('uploaded_files', lazy=True))

    def __repr__(self):
        return f'<ReportAttachment {self.id}: {self.original_filename}>'

    def get_formatted_size(self):
        return format_file_size(self.file_size)

    def get_icon_class(self):
        return get_file_icon(self.original_filename)

    def get_owner_id(self):
        """Return the folder name used for storing this file on disk"""
        if self.report_id:
            return f"report_{self.report_id}"
        return f"complaint_{self.complaint_id}"

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


def get_all_dynamic_templates():
    """
    Merge built-in PSR_DYNAMIC_TEMPLATES with active CustomTemplates.
    Returns a combined dict keyed by slug — safe to pass to Jinja and JS.
    Each entry includes a 'department' key (None = unassigned = visible to all).
    """
    combined = {}
    for slug, config in PSR_DYNAMIC_TEMPLATES.items():
        combined[slug] = dict(config)
        combined[slug].setdefault('department', None)   # built-ins unassigned until admin maps them
    try:
        custom = CustomTemplate.query.filter_by(is_active=True).all()
        for ct in custom:
            entry = ct.to_dynamic_config()
            entry['department'] = ct.department
            combined[ct.slug] = entry
    except Exception:
        pass
    return combined


def get_templates_for_user(user):
    """
    Return the subset of dynamic templates this user is allowed to submit.
    Admins, PSR dept, and zonal users get everything.
    HQ users get only templates matching their department + unassigned templates.
    """
    all_tpls = get_all_dynamic_templates()
    if user.can_view_all_reports():
        return all_tpls
    return {slug: cfg for slug, cfg in all_tpls.items()
            if user.can_submit_template(cfg.get('department'))}


def slugify(text):
    """Convert a name to a URL-safe slug."""
    import re
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\s_]', '', text)
    text = re.sub(r'[\s]+', '_', text)
    return text[:80]

def _build_status_of_complaint(description, date_time_str):
    """
    Combine status description text and datetime into a single stored string.
    e.g. "Under Investigation — 2026-03-05 14:30"
    """
    parts = []
    if description and description.strip():
        parts.append(description.strip())
    if date_time_str:
        try:
            dt = datetime.fromisoformat(date_time_str)
            parts.append(dt.strftime('%Y-%m-%d %H:%M'))
        except ValueError:
            parts.append(date_time_str)
    return ' — '.join(parts) if parts else None


def _save_attachments(req, report_id=None, complaint_id=None):
    """
    Process uploaded files from a form request and save to disk + database.
    Pass either report_id (ProgramReport) or complaint_id (ConsumerComplaint).
    Returns the number of files successfully saved.
    """
    if 'attachments' not in req.files:
        return 0

    files = req.files.getlist('attachments')
    saved = 0

    # Determine folder name and check existing count
    folder_key = f"report_{report_id}" if report_id else f"complaint_{complaint_id}"
    existing = ReportAttachment.query.filter_by(
        report_id=report_id,
        complaint_id=complaint_id
    ).count()

    for file in files:
        if not file or file.filename == '':
            continue
        if existing + saved >= MAX_FILES_PER_REPORT:
            flash(f'Maximum {MAX_FILES_PER_REPORT} files allowed per report. Some files were skipped.', 'warning')
            break

        success, unique_filename, error = save_file(file, folder_key)
        if not success:
            flash(f'Could not upload "{file.filename}": {error}', 'warning')
            continue

        try:
            file_path = get_file_path(folder_key, unique_filename)
            file_size = os.path.getsize(file_path)
            extension = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'unknown'

            attachment = ReportAttachment(
                report_id=report_id,
                complaint_id=complaint_id,
                filename=unique_filename,
                original_filename=secure_filename(file.filename),
                file_size=file_size,
                file_type=extension,
                uploaded_by=current_user.id
            )
            db.session.add(attachment)
            saved += 1
        except Exception as e:
            delete_file(folder_key, unique_filename)
            flash(f'Error saving "{file.filename}": {str(e)}', 'warning')

    if saved > 0:
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash('Attachments could not be saved to database.', 'danger')
            return 0

    return saved


def generate_otp():
    """Generate a cryptographically secure 8-digit OTP."""
    return ''.join(secrets.choice(string.digits) for _ in range(8))


def send_otp_email(user_email, user_name, otp):
    """Send OTP via M365 SMTP. Returns (success, error_message)."""
    smtp_server   = os.environ.get('MAIL_SERVER', 'smtp.office365.com')
    smtp_port     = int(os.environ.get('MAIL_PORT', 587))
    smtp_user     = os.environ.get('MAIL_USERNAME', '')
    smtp_password = os.environ.get('MAIL_PASSWORD', '')
    sender_email  = os.environ.get('MAIL_DEFAULT_SENDER', smtp_user)

    if not smtp_user or not smtp_password:
        # Dev fallback — print to console
        print(f"\n[MFA DEV] OTP for {user_email}: {otp}\n")
        return True, None

    subject = "FCCPC PSR — Your Login Verification Code"
    body = f"""Dear {user_name},

Your 8-digit verification code for the FCCPC Price Surveillance & Reporting System is:

    {otp}

This code expires in {OTP_EXPIRY_MINUTES} minutes.

If you did not attempt to log in, please contact your administrator immediately.

— FCCPC PSR System
"""
    try:
        msg = MIMEMultipart()
        msg['From']    = sender_email
        msg['To']      = user_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(sender_email, user_email, msg.as_string())
        return True, None
    except Exception as e:
        return False, str(e)

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
        office_type = request.form.get('office_type', 'zonal').strip()
        department = request.form.get('department', '').strip() or None

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
            office_type=office_type,
            department=department if office_type == 'HQ' else None,
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
    
    return render_template('register.html', states=NIGERIAN_STATES, departments=HQ_DEPARTMENTS)

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

            # MFA: generate 8-digit OTP, store in session, send email
            otp    = generate_otp()
            expiry = datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES)

            session['mfa_user_id']  = user.id
            session['mfa_otp']      = otp
            session['mfa_expiry']   = expiry.isoformat()
            session['mfa_attempts'] = 0

            success, error = send_otp_email(user.email, user.name, otp)
            if not success:
                flash(f'Could not send verification email: {error}. Contact administrator.', 'danger')
                session.clear()
                return redirect(url_for('login'))

            flash(f'A verification code has been sent to {user.email}.', 'info')
            return redirect(url_for('verify_otp'))
        else:
            flash('Invalid email or password.', 'danger')

    return render_template('login.html')


@app.route('/verify-otp', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def verify_otp():
    if 'mfa_user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['mfa_user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login'))

    if request.method == 'POST':
        entered_otp = request.form.get('otp', '').strip()

        # Check expiry
        expiry = datetime.fromisoformat(session.get('mfa_expiry', '2000-01-01'))
        if datetime.utcnow() > expiry:
            session.clear()
            flash('Verification code expired. Please log in again.', 'warning')
            return redirect(url_for('login'))

        # Max 5 attempts
        attempts = session.get('mfa_attempts', 0)
        if attempts >= 5:
            session.clear()
            flash('Too many incorrect attempts. Please log in again.', 'danger')
            log_action("MFA Failed", target_user=user,
                       details=f"{user.email} exceeded OTP attempts")
            return redirect(url_for('login'))

        if secrets.compare_digest(entered_otp, session.get('mfa_otp', '')):
            session.pop('mfa_user_id',  None)
            session.pop('mfa_otp',      None)
            session.pop('mfa_expiry',   None)
            session.pop('mfa_attempts', None)
            login_user(user)
            log_action(action="Login", details=f"{user.email} logged in (MFA passed)")
            flash('Logged in successfully!', 'success')
            return redirect(url_for('program_dashboard'))
        else:
            session['mfa_attempts'] = attempts + 1
            remaining = 5 - session['mfa_attempts']
            flash(f'Incorrect code. {remaining} attempt(s) remaining.', 'danger')

    masked_email = user.email[:3] + '***@' + user.email.split('@')[1]
    return render_template('verify_otp.html', masked_email=masked_email,
                           expiry_minutes=OTP_EXPIRY_MINUTES)

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
    role        = request.args.get('role')
    search      = request.args.get('search')
    office_type = request.args.get('office_type')

    query = User.query
    if role:
        try:
            query = query.filter(User.role == int(role))
        except ValueError:
            pass
    if search:
        query = query.filter(User.name.ilike(f'%{search}%') | User.email.ilike(f'%{search}%'))
    if office_type:
        query = query.filter(User.office_type == office_type)

    users = query.order_by(User.id.desc()).all()

    # FIX: Pass total counts separately so badges always show DB totals, not filtered
    total_users  = User.query.count()
    total_hq     = User.query.filter_by(office_type='HQ').count()
    total_zonal  = User.query.filter(User.office_type != 'HQ').count()
    total_active = User.query.filter_by(is_enabled=True).count()

    return render_template('admin_dashboard.html', users=users,
                           hq_departments=HQ_DEPARTMENTS,
                           total_users=total_users, total_hq=total_hq,
                           total_zonal=total_zonal, total_active=total_active)

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
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/edit-user/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    """Admin edits a user office type, department, and role."""
    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        office_type = request.form.get('office_type', 'Zonal/State').strip()
        department  = request.form.get('department', '').strip() or None
        role        = request.form.get('role', str(user.role)).strip()

        user.office_type = office_type
        user.department  = department if office_type == 'HQ' else None

        if user.id != current_user.id:
            try:
                new_role = int(role)
                if new_role in [1, 2, 3, 4, 9]:
                    user.role = new_role
            except ValueError:
                pass

        try:
            db.session.commit()
            log_action("User Edited", target_user=user,
                       details=f"office_type={office_type}, department={user.department}, role={user.role}")
            flash(f"{user.name} updated successfully.", 'success')
        except Exception as e:
            db.session.rollback()
            flash(f"Update failed: {str(e)}", 'danger')

        return redirect(url_for('admin_dashboard'))

    return render_template('edit_user.html', user=user, departments=HQ_DEPARTMENTS)


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

            # FIX: Server-side permission check
            all_dyn = get_all_dynamic_templates()
            if template_slug in all_dyn:
                tpl_dept = all_dyn[template_slug].get('department')
                if not current_user.can_submit_template(tpl_dept):
                    flash("You are not authorised to submit this report template.", "danger")
                    return redirect(url_for('program_report_form'))

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
                        dynamic_templates=get_all_dynamic_templates()
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
                    status_of_complaint=_build_status_of_complaint(
                        request.form.get('status_description'),
                        request.form.get('status_date_time')
                    ),
                    value_of_complaint=value_of_complaint,
                    date_of_resolution=date_of_resolution,
                    complainant_remark=complainant_remark
                )

                db.session.add(new_complaint)
                db.session.commit()

                # Process file attachments for complaint
                _save_attachments(request, complaint_id=new_complaint.id)

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
            
            # âœ… PHASE 1: Capture date_started and date_ended
            ds_str = request.form.get('date_started')
            date_started = datetime.strptime(ds_str, '%Y-%m-%d').date() if ds_str else datetime.utcnow().date()
            
            de_str = request.form.get('date_ended')  # âœ… NEW: Date Ended field
            date_ended = datetime.strptime(de_str, '%Y-%m-%d').date() if de_str else None

            new_report = ProgramReport(
                user_id=current_user.id,
                report_type=report_type,
                title=title,
                objective=objective,
                period_covered=request.form.get('period_covered', 'N/A'),
                date_started=date_started,
                date_ended=date_ended,  # âœ… NEW: Save date_ended
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

            elif template_slug in get_all_dynamic_templates():
                template_config = get_all_dynamic_templates()[template_slug]
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

            # Process file attachments for program report
            attach_count = _save_attachments(request, report_id=new_report.id)

            if is_draft:
                flash("Report saved as draft.", "info")
            else:
                if attach_count > 0:
                    flash(f"Report submitted successfully with {attach_count} attachment(s)!", "success")
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
                dynamic_templates=get_all_dynamic_templates()
            )

    # Build combined report types list and psr_templates dict
    # including active custom templates — filtered by user's department
    user_dynamic = get_templates_for_user(current_user)
    all_report_types = list(REPORT_TYPES)
    all_psr_templates = dict(PSR_TEMPLATES)
    try:
        custom_tpls = CustomTemplate.query.filter_by(is_active=True).all()
        for ct in custom_tpls:
            if not current_user.can_submit_template(ct.department):
                continue
            key = ct.name.upper()
            all_psr_templates[key] = {
                'code': ct.code,
                'slug': ct.slug,
                'category': ct.category,
                'requires_common_fields': False
            }
            all_report_types.append(key)
    except Exception:
        pass

    return render_template(
        'program_report_form.html',
        report_types=all_report_types,
        targets_list=TARGETS_ACHIEVED_LIST,
        psr_templates=all_psr_templates,
        dynamic_templates=user_dynamic
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

    if current_user.can_view_all_reports():
        pass  # Admin, PSR dept, Zonal/State — see everything
    elif current_user.is_hq():
        # HQ user: scope to own department's submissions
        psr_query = (psr_query.join(User)
                     .filter(User.department == current_user.department))
        # Within department, non-directors only see their own
        if not (current_user.is_director() or current_user.is_evc()):
            psr_query = psr_query.filter(ProgramReport.user_id == current_user.id)
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

    if current_user.can_view_all_reports():
        complaints = complaints_query.order_by(ConsumerComplaint.date_received.desc()).all()
    elif current_user.is_hq():
        q = complaints_query.join(User).filter(User.department == current_user.department)
        if not (current_user.is_director() or current_user.is_evc()):
            q = q.filter(ConsumerComplaint.user_id == current_user.id)
        complaints = q.order_by(ConsumerComplaint.date_received.desc()).all()
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

    # âœ… PHASE 1: Add result count for filtered/searched results
    result_count = len(all_reports)

    # CALCULATE UNIFIED STATS (without filters for accurate totals)
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)
    seven_days_ago = now - timedelta(days=7)
    
    # PSR stats
    # FIX 3: Stats use can_view_all_reports() consistently
    psr_total_query = ProgramReport.query
    if current_user.can_view_all_reports():
        pass
    elif current_user.is_hq():
        psr_total_query = psr_total_query.join(User).filter(User.department == current_user.department)
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
    if current_user.can_view_all_reports():
        all_complaints = complaints_total_query.all()
    elif current_user.is_hq():
        all_complaints = complaints_total_query.join(User).filter(User.department == current_user.department).all()
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

    # Pass custom templates for dashboard filter dropdown
    try:
        custom_tpls_for_filter = CustomTemplate.query.filter_by(is_active=True).all()
    except Exception:
        custom_tpls_for_filter = []

    return render_template(
        "program_dashboard.html",
        reports=all_reports,
        templates=PSR_TEMPLATES,
        custom_templates=custom_tpls_for_filter,
        stats=stats,
        result_count=result_count,
        view_title="Program Status Reports"
    )

# âœ… PHASE 1: NEW ROUTE - Complaints Analytics
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

# âœ… PHASE 1: Export Complaints Analytics to Excel
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

# ==================== CUSTOM TEMPLATE BUILDER ====================

@app.route('/admin/templates')
@login_required
def custom_templates_list():
    if not current_user.is_admin():
        abort(403)
    templates = CustomTemplate.query.order_by(CustomTemplate.created_at.desc()).all()
    # Count reports per custom template
    for ct in templates:
        ct.report_count = ProgramReport.query.filter_by(report_type=ct.slug).count()
    return render_template('admin/template_builder.html',
                           templates=templates, page='list')


@app.route('/admin/templates/new', methods=['GET', 'POST'])
@login_required
def custom_template_new():
    if not current_user.is_admin():
        abort(403)

    if request.method == 'POST':
        data = request.get_json()
        if not data:
            return json.dumps({'error': 'No data received'}), 400

        name     = data.get('name', '').strip()
        code     = data.get('code', '').strip().upper()
        category = data.get('category', 'custom').strip()
        fields   = data.get('fields', [])

        if not name or not code:
            return json.dumps({'error': 'Name and Code are required.'}), 400
        if not fields:
            return json.dumps({'error': 'At least one field is required.'}), 400

        # Generate unique slug
        base_slug = slugify(name)
        slug = base_slug
        counter = 1
        while CustomTemplate.query.filter_by(slug=slug).first():
            slug = f"{base_slug}_{counter}"
            counter += 1

        try:
            ct = CustomTemplate(
                name=name, code=code, slug=slug,
                category=category, created_by=current_user.id
            )
            db.session.add(ct)
            db.session.flush()

            for i, field_data in enumerate(fields):
                label    = field_data.get('label', '').strip()
                ftype    = field_data.get('type', 'text')
                required = field_data.get('required', False)
                opts     = field_data.get('options', [])
                if not label:
                    continue
                fkey = slugify(label) or f'field_{i}'
                cf = CustomTemplateField(
                    template_id=ct.id,
                    field_key=fkey,
                    label=label,
                    field_type=ftype,
                    options=json.dumps(opts) if opts else None,
                    is_required=required,
                    sort_order=i
                )
                db.session.add(cf)

            db.session.commit()
            log_action("Custom Template Created", details=f"Created template: {name} ({code})")
            return json.dumps({'success': True, 'slug': slug, 'id': ct.id})

        except Exception as e:
            db.session.rollback()
            return json.dumps({'error': str(e)}), 500

    return render_template('admin/template_builder.html', page='new')


@app.route('/admin/templates/<int:template_id>/edit', methods=['GET', 'POST'])
@login_required
def custom_template_edit(template_id):
    if not current_user.is_admin():
        abort(403)
    ct = CustomTemplate.query.get_or_404(template_id)

    if request.method == 'POST':
        data = request.get_json()
        if not data:
            return json.dumps({'error': 'No data received'}), 400

        name     = data.get('name', '').strip()
        code     = data.get('code', '').strip().upper()
        category = data.get('category', ct.category).strip()
        fields   = data.get('fields', [])
        is_active = data.get('is_active', ct.is_active)

        if not name or not code:
            return json.dumps({'error': 'Name and Code are required.'}), 400

        try:
            ct.name      = name
            ct.code      = code
            ct.category  = category
            ct.is_active = is_active

            # Replace all fields
            CustomTemplateField.query.filter_by(template_id=ct.id).delete()
            for i, field_data in enumerate(fields):
                label    = field_data.get('label', '').strip()
                ftype    = field_data.get('type', 'text')
                required = field_data.get('required', False)
                opts     = field_data.get('options', [])
                if not label:
                    continue
                fkey = slugify(label) or f'field_{i}'
                cf = CustomTemplateField(
                    template_id=ct.id,
                    field_key=fkey,
                    label=label,
                    field_type=ftype,
                    options=json.dumps(opts) if opts else None,
                    is_required=required,
                    sort_order=i
                )
                db.session.add(cf)

            db.session.commit()
            log_action("Custom Template Edited", details=f"Edited template: {name} ({code})")
            return json.dumps({'success': True})

        except Exception as e:
            db.session.rollback()
            return json.dumps({'error': str(e)}), 500

    # GET — return template data as JSON for the builder to load
    ct_data = {
        'id':        ct.id,
        'name':      ct.name,
        'code':      ct.code,
        'category':  ct.category,
        'is_active': ct.is_active,
        'fields': [
            {
                'label':    f.label,
                'type':     f.field_type,
                'required': f.is_required,
                'options':  json.loads(f.options) if f.options else [],
            }
            for f in ct.fields
        ]
    }
    return render_template('admin/template_builder.html',
                           page='edit', ct=ct, ct_json=json.dumps(ct_data))


@app.route('/admin/templates/<int:template_id>/delete', methods=['POST'])
@login_required
def custom_template_delete(template_id):
    if not current_user.is_admin():
        abort(403)
    ct = CustomTemplate.query.get_or_404(template_id)
    report_count = ProgramReport.query.filter_by(report_type=ct.slug).count()

    if report_count > 0:
        flash(f'Cannot delete "{ct.name}" — {report_count} report(s) exist against this template. Deactivate it instead.', 'danger')
        return redirect(url_for('custom_templates_list'))

    name = ct.name
    try:
        db.session.delete(ct)
        db.session.commit()
        log_action("Custom Template Deleted", details=f"Deleted template: {name}")
        flash(f'Template "{name}" deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Delete failed: {str(e)}', 'danger')

    return redirect(url_for('custom_templates_list'))


@app.route('/admin/templates/<int:template_id>/toggle', methods=['POST'])
@login_required
def custom_template_toggle(template_id):
    if not current_user.is_admin():
        abort(403)
    ct = CustomTemplate.query.get_or_404(template_id)
    ct.is_active = not ct.is_active
    db.session.commit()
    state = 'activated' if ct.is_active else 'deactivated'
    flash(f'Template "{ct.name}" {state}.', 'success')
    return redirect(url_for('custom_templates_list'))


# ==================== AUTO-FILL PARSE ROUTE ====================

@app.route('/psr/parse-upload', methods=['POST'])
@login_required
def parse_autofill_upload():
    """
    Server-side parser for .docx files uploaded for auto-fill.
    Returns JSON: { headers: [...], rows: [[...], [...]] }
    """
    from flask import jsonify

    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded.'}), 400

    file = request.files['file']
    if not file.filename.lower().endswith('.docx'):
        return jsonify({'error': 'Only .docx files are handled server-side.'}), 400

    try:
        import docx as python_docx
        doc = python_docx.Document(file)

        # Look for the first table with at least 2 rows
        table = None
        for t in doc.tables:
            if len(t.rows) >= 2:
                table = t
                break

        if table is None:
            return jsonify({
                'error': (
                    'No data table found in this Word document. '
                    'This document appears to contain narrative text only and '
                    'cannot be auto-filled. Please fill the form manually.'
                )
            }), 200

        # Extract headers from first row (clean bold markers, strip whitespace)
        headers = []
        for cell in table.rows[0].cells:
            text = cell.text.strip()
            # Remove duplicate merged cell text (Word sometimes duplicates)
            if text not in headers:
                headers.append(text)
            else:
                headers.append('')  # blank placeholder for merged cols

        # Extract data rows
        rows = []
        for row in table.rows[1:]:
            cells = [cell.text.strip() for cell in row.cells]
            # Only include rows that have at least one non-empty cell
            if any(c for c in cells):
                # Trim to match header count
                rows.append(cells[:len(headers)])

        if not rows:
            return jsonify({'error': 'Table found but contains no data rows.'}), 200

        return jsonify({'headers': headers, 'rows': rows})

    except Exception as e:
        return jsonify({'error': f'Could not read Word file: {str(e)}'}), 500


# ==================== ATTACHMENT ROUTES ====================

@app.route('/attachment/download/<int:attachment_id>')
@login_required
def download_attachment(attachment_id):
    """Download a file attachment"""
    attachment = ReportAttachment.query.get_or_404(attachment_id)

    # Authorization check
    if attachment.report_id:
        owner_id = ProgramReport.query.get_or_404(attachment.report_id).user_id
    else:
        owner_id = ConsumerComplaint.query.get_or_404(attachment.complaint_id).user_id

    if not current_user.is_admin() and not current_user.is_supervisor() and current_user.id != owner_id:
        abort(403)

    folder_key = attachment.get_owner_id()
    file_path = get_file_path(folder_key, attachment.filename)
    directory = os.path.dirname(file_path)

    log_action("File Downloaded", details=f"Downloaded {attachment.original_filename} (attachment #{attachment.id})")

    return send_from_directory(
        directory,
        attachment.filename,
        as_attachment=True,
        download_name=attachment.original_filename
    )


@app.route('/attachment/delete/<int:attachment_id>', methods=['POST'])
@login_required
def delete_attachment(attachment_id):
    """Delete a file attachment"""
    attachment = ReportAttachment.query.get_or_404(attachment_id)

    # Determine parent report/complaint and redirect target
    if attachment.report_id:
        parent = ProgramReport.query.get_or_404(attachment.report_id)
        owner_id = parent.user_id
        redirect_url = url_for('view_program_report', report_id=parent.id)
    else:
        parent = ConsumerComplaint.query.get_or_404(attachment.complaint_id)
        owner_id = parent.user_id
        redirect_url = url_for('view_program_report', report_id=parent.id) + '?type=complaint'

    if not current_user.is_admin() and current_user.id != owner_id:
        abort(403)

    folder_key = attachment.get_owner_id()
    original_name = attachment.original_filename

    # Delete physical file
    delete_file(folder_key, attachment.filename)

    # Delete database record
    try:
        db.session.delete(attachment)
        db.session.commit()
        log_action("File Deleted", details=f"Deleted {original_name} (attachment #{attachment_id})")
        flash(f'"{original_name}" deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting file: {str(e)}', 'danger')

    return redirect(redirect_url)


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
        
        all_dynamic = get_all_dynamic_templates()
        if template_slug in all_dynamic:
            config = all_dynamic[template_slug]
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
    
    all_dynamic = get_all_dynamic_templates()
    if report.report_type not in all_dynamic:
        flash("Export only available for dynamic templates", "warning")
        return redirect(url_for("view_program_report", report_id=report.id))
    
    config = all_dynamic[report.report_type]
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
    with app.app_context():
        init_upload_folder()
    app.run(debug=True)
