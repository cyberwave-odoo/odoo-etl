from odoo import models, fields

class EtlLog(models.Model):
    _name = 'etl.log'
    _description = 'ETL Execution Log'
    _order = 'create_date desc'

    etl_model_id = fields.Many2one('etl.model', string='ETL Model', ondelete='cascade', required=True, index=True)
    log_type = fields.Selection([
        ('error', 'Error'),
        ('warning', 'Warning'),
        ('info', 'Info'),
    ], string='Log Type', required=True, index=True)
    message = fields.Text('Log Message', required=True)
    record_data = fields.Text('Failed Record Data')
    run_date = fields.Datetime('Run Date', default=fields.Datetime.now, required=True)
