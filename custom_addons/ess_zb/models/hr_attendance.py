# models/hr_attendance.py

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import math
from odoo.tools import format_datetime
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

    def _is_user_admin(self):
        """Check if current user is an administrator"""
        return self.env.user.has_group('hr_attendance.group_hr_attendance_manager') or \
               self.env.user.has_group('base.group_system')

    def _validate_geofence(self, latitude, longitude, employee):
        """Validate if coordinates are within allowed geofence for specific employee"""
        assigned_locations = employee.attendance_location_ids.filtered(lambda l: l.active)
        
        if not assigned_locations:
            assigned_locations = self.env['hr.attendance.location'].sudo().search([
                ('company_id', '=', self.env.company.id),
                ('active', '=', True),
                ('employee_ids', '=', False)
            ])
        
        if not assigned_locations:
            return False, 0, None
        
        for location in assigned_locations:
            distance = self._calculate_distance(
                latitude, longitude,
                location.latitude, location.longitude
            )
            if distance <= location.radius_km:
                return True, distance, location
        
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

    def _format_datetime_user_tz(self, dt):
        """Format datetime in user's timezone"""
        if not dt:
            return False
        
        tz = self.env.user.tz or 'UTC'
        
        try:
            if dt.tzinfo is None:
                utc_dt = pytz.UTC.localize(dt)
            else:
                utc_dt = dt
            
            user_tz = pytz.timezone(tz)
            local_dt = utc_dt.astimezone(user_tz)
            
            return local_dt.strftime('%Y-%m-%d %I:%M:%S %p')
        except Exception as e:
            return format_datetime(self.env, dt, dt_format='yyyy-MM-dd hh:mm:ss a')

    @api.model
    def employee_check_in(self, latitude=None, longitude=None):
        """Method for employee to check in with location and geofencing"""
        employee = self.env.user.employee_id
        if not employee:
            raise UserError(_('No employee linked to this user.'))
        
        is_admin = self._is_user_admin()
        
        if not is_admin and (not latitude or not longitude):
            raise UserError(_('Location is required for check-in. Please enable GPS/location services.'))
        
        distance = 0
        location = None
        
        if not is_admin:
            if latitude and longitude:
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
        
        existing_open = attendance_sudo.search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False)
        ], limit=1)
        
        if existing_open:
            raise UserError(_('You are already checked in.'))
        
        vals = {
            'employee_id': employee.id,
            'check_in': fields.Datetime.now(),
            'check_in_latitude': latitude if latitude else 0.0,
            'check_in_longitude': longitude if longitude else 0.0,
            'is_within_geofence': True,
            'distance_from_office': distance,
        }
        
        if location:
            vals['attendance_location_id'] = location.id
        
        attendance = attendance_sudo.create(vals)
        
        return {
            'id': attendance.id,
            'employee_id': attendance.employee_id.id,
            'check_in': self._format_datetime_user_tz(attendance.check_in),
            'is_within_geofence': True,
            'location_name': location.name if location else 'Admin Override',
            'is_admin': is_admin,
        }

    @api.model
    def employee_check_out(self, latitude=None, longitude=None):
        """Method for employee to check out with location"""
        employee = self.env.user.employee_id
        if not employee:
            raise UserError(_('No employee linked to this user.'))
        
        is_admin = self._is_user_admin()
        
        if not is_admin and (not latitude or not longitude):
            raise UserError(_('Location is required for check-out. Please enable GPS/location services.'))
        
        attendance_sudo = self.sudo()
        
        attendance = attendance_sudo.search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False)
        ], limit=1)
        
        if not attendance:
            raise UserError(_('You are not checked in.'))
        
        vals = {
            'check_out': fields.Datetime.now(),
            'check_out_latitude': latitude if latitude else 0.0,
            'check_out_longitude': longitude if longitude else 0.0,
        }
        
        attendance.write(vals)
        
        return {
            'id': attendance.id,
            'check_out': self._format_datetime_user_tz(attendance.check_out),
            'worked_hours': attendance.worked_hours,
            'is_admin': is_admin,
        }

    @api.model
    def get_employee_attendance_status(self):
        """Get current attendance status for logged-in employee"""
        try:
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
                'check_in_time': self._format_datetime_user_tz(attendance.check_in) if attendance else False,
                'attendance_id': attendance.id if attendance else False,
                'is_admin': self._is_user_admin(),
            }
        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.error(f"Error in get_employee_attendance_status: {str(e)}")
            return {'error': str(e)}
