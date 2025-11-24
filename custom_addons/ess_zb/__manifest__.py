{
    'name': 'Employee Self Attendance with Location',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Attendances',
    'summary': 'Employee check in/out with geolocation and geofencing',
    'description': """
Employee Self Attendance with Geolocation & Geofencing
=======================================================
* Check in and check out with automatic geolocation capture
* Geofencing validation to ensure check-in within allowed areas
* View attendance dashboard with real-time status
* Track check-in and check-out locations using GPS coordinates
    """,
    'author': 'Zingbizz',
    'website': 'https://zingbizz.com',
    'license': 'LGPL-3',
    'depends': ['hr_attendance', 'web'],
    'data': [
        'security/hr_attendance_security.xml',
        'security/ir.model.access.csv',
        'views/hr_attendance_views.xml',
        'views/attendance_dashboard.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ess_zb/static/src/js/attendance_dashboard.js',
            'ess_zb/static/src/xml/attendance_dashboard.xml',
        ],
    },
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
