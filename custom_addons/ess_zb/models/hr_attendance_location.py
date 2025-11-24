# models/hr_attendance_location.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class HrAttendanceLocation(models.Model):
    _name = 'hr.attendance.location'
    _description = 'Allowed Attendance Locations'

    name = fields.Char(string='Location Name', required=True)
    latitude = fields.Float(string='Latitude', required=True, digits=(10, 7))
    longitude = fields.Float(string='Longitude', required=True, digits=(10, 7))
    radius_km = fields.Float(string='Allowed Radius (km)', required=True, default=0.5)
    address = fields.Text(string='Address')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    active = fields.Boolean(string='Active', default=True)
    
    # Employee assignment
    employee_ids = fields.Many2many(
        'hr.employee', 
        'hr_attendance_location_employee_rel', 
        'location_id', 
        'employee_id',
        string='Assigned Employees'
    )
    employee_count = fields.Integer(
        string='Employee Count', 
        compute='_compute_employee_count',
        store=True
    )
    
    @api.depends('employee_ids')
    def _compute_employee_count(self):
        for record in self:
            record.employee_count = len(record.employee_ids)
    
    @api.constrains('radius_km')
    def _check_radius(self):
        for record in self:
            if record.radius_km <= 0:
                raise ValidationError(_('Radius must be greater than 0.'))
