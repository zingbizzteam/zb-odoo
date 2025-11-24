# models/hr_employee.py
from odoo import models, fields

class HrEmployee(models.Model):
    _inherit = 'hr.employee'
    
    attendance_location_ids = fields.Many2many(
        'hr.attendance.location',
        'hr_attendance_location_employee_rel',
        'employee_id',
        'location_id',
        string='Allowed Attendance Locations'
    )
