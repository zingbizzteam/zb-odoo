# models/hr_attendance.py

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import math
from datetime import datetime, timedelta
import pytz

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'
    
    check_in_latitude = fields.Float(string='Check In Latitude', digits=(10, 7))
    check_in_longitude = fields.Float(string='Check In Longitude', digits=(10, 7))
    check_out_latitude = fields.Float(string='Check Out Latitude', digits=(10, 7))
    check_out_longitude = fields.Float(string='Check Out Longitude', digits=(10, 7))
    check_in_location = fields.Char(string='Check In Location', compute='_compute_check_in_location', store=True)
    check_out_location = fields.Char(string='Check Out Location', compute='_compute_check_out_location', store=True)
    is_within_geofence = fields.Boolean(string='Within Geofence', default=False)
    distance_from_office = fields.Float(string='Distance from Office (km)', digits=(10, 2))
    attendance_location_id = fields.Many2one('hr.attendance.location', string='Check-in Location')
    auto_checkout = fields.Boolean(string='Auto Checkout', default=False)
    
    @api.depends('check_in_latitude', 'check_in_longitude')
    def _compute_check_in_location(self):
        for record in self:
            if record.check_in_latitude and record.check_in_longitude:
                record.check_in_location = f"{record.check_in_latitude}, {record.check_in_longitude}"
            else:
                record.check_in_location = False
    
    @api.depends('check_out_latitude', 'check_out_longitude')
    def _compute_check_out_location(self):
        for record in self:
            if record.check_out_latitude and record.check_out_longitude:
                record.check_out_location = f"{record.check_out_latitude}, {record.check_out_longitude}"
            else:
                record.check_out_location = False
    
    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two coordinates using Haversine formula"""
        R = 6371  # Earth's radius in kilometers
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) * math.sin(dlat / 2) +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon / 2) * math.sin(dlon / 2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c
        return distance
    
    def _validate_geofence(self, latitude, longitude, employee):
        """Validate if coordinates are within allowed geofence for specific employee"""
        # Get employee's assigned locations
        assigned_locations = employee.attendance_location_ids.filtered(lambda l: l.active)
        
        if not assigned_locations:
            # If no locations assigned, check company-wide locations
            assigned_locations = self.env['hr.attendance.location'].sudo().search([
                ('company_id', '=', self.env.company.id),
                ('active', '=', True),
                ('employee_ids', '=', False)  # Locations without specific employee assignment
            ])
        
        if not assigned_locations:
            # No geofencing configured - throw error
            return False, 0, None
        
        # Check if within any allowed location
        for location in assigned_locations:
            distance = self._calculate_distance(
                latitude, longitude,
                location.latitude, location.longitude
            )
            if distance <= location.radius_km:
                return True, distance, location
        
        # Find nearest allowed location for error message
        nearest_distance = float('inf')
        nearest_location = None
        for location in assigned_locations:
            distance = self._calculate_distance(
                latitude, longitude,
                location.latitude, location.longitude
            )
            if distance < nearest_distance:
                nearest_distance = distance
                nearest_location = location
        
        return False, nearest_distance, nearest_location
    
    def _convert_to_user_timezone(self, dt):
        """Convert UTC datetime to user's timezone"""
        if not dt:
            return False
        
        # Get user's timezone
        tz_name = self.env.user.tz or 'UTC'
        user_tz = pytz.timezone(tz_name)
        
        # Convert from UTC to user timezone
        if isinstance(dt, str):
            dt = fields.Datetime.from_string(dt)
        
        utc_dt = pytz.UTC.localize(dt) if not dt.tzinfo else dt
        user_dt = utc_dt.astimezone(user_tz)
        
        return user_dt.strftime('%Y-%m-%d %H:%M:%S')
    
    @api.model
    def employee_check_in(self, latitude=None, longitude=None):
        """Method for employee to check in with location and geofencing"""
        employee = self.env.user.employee_id
        if not employee:
            raise UserError(_('No employee linked to this user.'))
        
        # ENFORCE LOCATION REQUIREMENT
        if not latitude or not longitude:
            raise UserError(_('Location is required for check-in. Please enable GPS/location services.'))
        
        # Validate geofencing
        is_valid, distance, location = self._validate_geofence(latitude, longitude, employee)
        
        if not is_valid:
            if location:
                raise UserError(
                    _('You are %.2f km away from %s. Please check in within %.2f km radius.') % 
                    (distance, location.name, location.radius_km)
                )
            else:
                raise UserError(_('No attendance locations configured. Contact your HR manager.'))
        
        attendance_sudo = self.sudo()
        
        # Check if already checked in
        existing_open = attendance_sudo.search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False)
        ], limit=1)
        
        if existing_open:
            raise UserError(_('You are already checked in.'))
        
        # Create check-in record
        vals = {
            'employee_id': employee.id,
            'check_in': fields.Datetime.now(),
            'check_in_latitude': latitude,
            'check_in_longitude': longitude,
            'is_within_geofence': True,
            'distance_from_office': distance,
        }
        
        if location:
            vals['attendance_location_id'] = location.id
        
        attendance = attendance_sudo.create(vals)
        
        return {
            'id': attendance.id,
            'employee_id': attendance.employee_id.id,
            'check_in': self._convert_to_user_timezone(attendance.check_in),
            'is_within_geofence': True,
            'location_name': location.name if location else False,
        }
    
    @api.model
    def employee_check_out(self, latitude=None, longitude=None):
        """Method for employee to check out with location"""
        employee = self.env.user.employee_id
        if not employee:
            raise UserError(_('No employee linked to this user.'))
        
        # ENFORCE LOCATION REQUIREMENT
        if not latitude or not longitude:
            raise UserError(_('Location is required for check-out. Please enable GPS/location services.'))
        
        attendance_sudo = self.sudo()
        
        # Find open attendance record
        attendance = attendance_sudo.search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False)
        ], limit=1)
        
        if not attendance:
            raise UserError(_('You are not checked in.'))
        
        vals = {
            'check_out': fields.Datetime.now(),
            'check_out_latitude': latitude,
            'check_out_longitude': longitude,
        }
        
        attendance.write(vals)
        
        return {
            'id': attendance.id,
            'check_out': self._convert_to_user_timezone(attendance.check_out),
            'worked_hours': attendance.worked_hours,
        }
    
    @api.model
    def get_employee_attendance_status(self):
        """Get current attendance status for logged-in employee"""
        employee = self.env.user.employee_id
        if not employee:
            return {'error': 'No employee linked to this user'}
        
        attendance = self.sudo().search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False)
        ], limit=1)
        
        return {
            'employee_name': employee.name,
            'is_checked_in': bool(attendance),
            'check_in_time': self._convert_to_user_timezone(attendance.check_in) if attendance else False,
            'attendance_id': attendance.id if attendance else False,
            'worked_hours': attendance.worked_hours if attendance else 0,
        }
    
    @api.model
    def _cron_auto_checkout(self):
        """Cron job to auto checkout employees after office hours"""
        # Get all open attendances
        open_attendances = self.sudo().search([
            ('check_out', '=', False)
        ])
        
        for attendance in open_attendances:
            employee = attendance.employee_id
            location = attendance.attendance_location_id
            
            # Get office end time (default 6 PM if not configured)
            office_end_hour = location.office_end_time if location else 18.0
            
            # Get user timezone
            tz_name = employee.user_id.tz or 'UTC'
            user_tz = pytz.timezone(tz_name)
            
            # Get current time in user's timezone
            utc_now = datetime.now(pytz.UTC)
            user_now = utc_now.astimezone(user_tz)
            
            # Convert check_in to user timezone
            check_in_utc = pytz.UTC.localize(attendance.check_in)
            check_in_user = check_in_utc.astimezone(user_tz)
            
            # Calculate office end time for that day
            office_end = check_in_user.replace(
                hour=int(office_end_hour),
                minute=int((office_end_hour % 1) * 60),
                second=0,
                microsecond=0
            )
            
            # If current time > office end time, auto checkout
            if user_now > office_end:
                # Auto checkout at office end time
                checkout_time_user = office_end
                checkout_time_utc = checkout_time_user.astimezone(pytz.UTC).replace(tzinfo=None)
                
                attendance.write({
                    'check_out': checkout_time_utc,
                    'auto_checkout': True,
                    'check_out_latitude': attendance.check_in_latitude,
                    'check_out_longitude': attendance.check_in_longitude,
                })
