from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging
from sqlalchemy import text, inspect

_logger = logging.getLogger(__name__)


class ETLMappingWizard(models.TransientModel):
    _name = 'etl.mapping.wizard'
    _description = 'ETL Mapping Generator - Dynamic Column Matching'

    # Step 1: Table/Model Selection
    dbsource_id = fields.Many2one('base.external.dbsource', string='Database Source', required=True)
    legacy_table_name = fields.Char(string='Legacy Table Name', required=True, help='Name of the legacy table (e.g., classes)')
    odoo_model_name = fields.Char(string='Odoo Model Name', required=True, help='Technical name of the Odoo model (e.g., op.batch)')

    # Step 2: Configuration
    unique_identifier_tuple = fields.Char(string='Unique Identifier Tuple', help="e.g., ('code', ('no_classe','year'))")
    arguments = fields.Text(string='Arguments', help='Pipe-separated arguments (e.g., start_date = ... | end_date = ...)')
    remove_condition = fields.Char(string='Remove Condition', help='Filter condition (e.g., pl.col("active") == True)')

    # Checkboxes
    custom_import = fields.Boolean(string='Custom Import', default=False)
    pre_exec = fields.Boolean(string='Pre Execution', default=False)
    bulk_import = fields.Boolean(string='Bulk Import', default=False)
    dry_run = fields.Boolean(string='Dry Run', default=False)

    # Step 3: Dynamic Mapping Lines
    mapping_line_ids = fields.One2many('etl.mapping.wizard.line', 'wizard_id', string='Field Mappings')

    # State management
    state = fields.Selection([
        ('select', 'Select Tables'),
        ('map', 'Map Fields'),
        ('review', 'Review'),
    ], default='select', string='State')

    # Store reference to original ETL model for updates
    etl_model_id = fields.Many2one('etl.model', string='ETL Model', readonly=True)

    def action_load_columns(self):
        """Load columns from both legacy table and Odoo model"""
        self.ensure_one()

        if not self.dbsource_id:
            raise UserError(_('Please select a database source'))
        if not self.legacy_table_name:
            raise UserError(_('Please enter a legacy table name'))
        if not self.odoo_model_name:
            raise UserError(_('Please enter an Odoo model name'))

        if self.odoo_model_name not in self.env:
            raise UserError(_('Model %s does not exist') % self.odoo_model_name)

        try:
            # Clear existing mapping lines first to avoid validation errors
            self.mapping_line_ids.unlink()

            # Clear existing transient records
            self.env['etl.mapping.wizard.odoo.field'].search([('wizard_id', '=', self.id)]).unlink()
            self.env['etl.mapping.wizard.legacy.column'].search([('wizard_id', '=', self.id)]).unlink()

            # Get and store Odoo model fields
            odoo_fields = self.env[self.odoo_model_name].fields_get()
            for field_name, field_info in sorted(odoo_fields.items()):
                if field_info.get('readonly') or field_info.get('store') == False:
                    continue

                self.env['etl.mapping.wizard.odoo.field'].create({
                    'wizard_id': self.id,
                    'field_name': field_name,
                    'field_label': field_info.get('string', field_name),
                })

            # Get and store legacy table columns
            legacy_columns = self._get_legacy_table_columns(self.legacy_table_name)
            for column in legacy_columns:
                self.env['etl.mapping.wizard.legacy.column'].create({
                    'wizard_id': self.id,
                    'column_name': column,
                })

            # Create new mapping lines
            mapping_lines = []
            for field_name, field_info in sorted(odoo_fields.items()):
                if field_info.get('readonly') or field_info.get('store') == False:
                    continue

                mapping_lines.append((0, 0, {
                    'odoo_field': field_name,
                    'odoo_field_type': field_info.get('type', 'char'),
                    'odoo_field_label': field_info.get('string', field_name),
                    'mapping_type': 'column',
                }))

            self.with_context(default_wizard_id=self.id).write({
                'mapping_line_ids': mapping_lines,
            })

            self.write({'state': 'map'})

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'etl.mapping.wizard',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }

        except Exception as e:
            _logger.error("Error loading columns: %s", str(e), exc_info=True)
            raise UserError(_('Error loading columns: %s') % str(e))

    def _get_legacy_table_columns(self, table_name):
        """Get columns from legacy database table"""
        dbsource = self.dbsource_id

        if dbsource.connector == 'sqlite':
            # Use PRAGMA table_info for SQLite
            data, cols = dbsource.execute_sqlite(text(f"PRAGMA table_info({table_name});"), (), metadata=True)
            # Column info is at index 1 of each row
            columns = [row[1] for row in data]
            return columns
        else:
            # For other databases, use SQLAlchemy inspector
            engine = dbsource._get_engine()
            inspector = inspect(engine)
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            return columns

    def action_generate_mapping(self):
        """Generate JSON field mapping and create/update ETL model record"""
        self.ensure_one()

        if not self.mapping_line_ids:
            raise UserError(_('Please configure at least one field mapping'))

        try:
            # Build field mapping as Python dict string (lambdas must be executable code)
            lines = ["{"]

            for line in self.mapping_line_ids:
                if not line.odoo_field:
                    continue

                if line.mapping_type == 'column':
                    if not line.legacy_column:
                        continue
                    lines.append(f"    '{line.odoo_field}': {{")
                    lines.append(f"        'type': 'column',")
                    lines.append(f"        'column_name': '{line.legacy_column}',")
                    if line.data_type:
                        lines.append(f"        'data_type': '{line.data_type}',")
                    lines.append(f"    }},")

                elif line.mapping_type == 'lambda':
                    if not line.lambda_function:
                        continue
                    lines.append(f"    '{line.odoo_field}': {{")
                    lines.append(f"        'type': 'lambda',")
                    # Lambda must be executable code, not a string
                    # Clean up the lambda function - remove trailing commas and 'function': prefix if present
                    lambda_str = line.lambda_function.strip().rstrip(',').strip()
                    # Remove 'function': prefix if user accidentally included it
                    if lambda_str.startswith("'function':"):
                        lambda_str = lambda_str[11:].strip()
                    elif lambda_str.startswith('"function":'):
                        lambda_str = lambda_str[11:].strip()
                    lines.append(f"        'function': {lambda_str},")
                    if line.data_type:
                        lines.append(f"        'data_type': '{line.data_type}',")
                    lines.append(f"    }},")

                elif line.mapping_type == 'join':
                    if not line.join_lookup_table or not line.join_left_on or not line.join_right_on:
                        continue
                    lines.append(f"    '{line.odoo_field}': {{")
                    lines.append(f"        'type': 'join',")
                    lines.append(f"        'lookup_table': '{line.join_lookup_table}',")
                    lines.append(f"        'left_on': '{line.join_left_on}',")
                    lines.append(f"        'right_on': '{line.join_right_on}',")
                    if line.join_model_field:
                        lines.append(f"        'model_field': '{line.join_model_field}',")
                    if line.data_type:
                        lines.append(f"        'data_type': '{line.data_type}',")
                    lines.append(f"    }},")

            lines.append("}")
            field_mapping_json = "\n".join(lines)

            # Create or update ETL model record
            vals = {
                'field_mapping': field_mapping_json,
                'unique_identifier_tuple': self.unique_identifier_tuple or '',
                'arguments': self.arguments or '',
                'remove_condition': self.remove_condition or '',
                'custom_import': self.custom_import,
                'pre_exec': self.pre_exec,
                'bulk_import': self.bulk_import,
                'dry_run': self.dry_run,
            }

            # If wizard was opened from an existing ETL model, update it
            if self.etl_model_id:
                self.etl_model_id.write(vals)
                message = _('ETL model updated successfully!')
            else:
                # Check if ETL model already exists
                existing = self.env['etl.model'].search([
                    ('name', '=', self.legacy_table_name),
                    ('odoo_name', '=', self.odoo_model_name)
                ], limit=1)

                if existing:
                    vals.update({
                        'name': self.legacy_table_name,
                        'odoo_name': self.odoo_model_name,
                        'dbsource_id': self.dbsource_id.id,
                    })
                    existing.write(vals)
                    message = _('ETL model updated successfully!')
                else:
                    vals.update({
                        'name': self.legacy_table_name,
                        'odoo_name': self.odoo_model_name,
                        'dbsource_id': self.dbsource_id.id,
                    })
                    self.env['etl.model'].create(vals)
                    message = _('ETL model created successfully!')

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }

        except Exception as e:
            raise UserError(_('Error generating mapping: %s') % str(e))


class ETLMappingWizardOdooField(models.TransientModel):
    """Store available Odoo fields for selection"""
    _name = 'etl.mapping.wizard.odoo.field'
    _description = 'Available Odoo Fields'

    wizard_id = fields.Many2one('etl.mapping.wizard', string='Wizard', required=True, ondelete='cascade')
    field_name = fields.Char(string='Field Name', required=True)
    field_label = fields.Char(string='Field Label')


class ETLMappingWizardLegacyColumn(models.TransientModel):
    """Store available legacy columns for selection"""
    _name = 'etl.mapping.wizard.legacy.column'
    _description = 'Available Legacy Columns'

    wizard_id = fields.Many2one('etl.mapping.wizard', string='Wizard', required=True, ondelete='cascade')
    column_name = fields.Char(string='Column Name', required=True)


class ETLMappingWizardLine(models.TransientModel):
    _name = 'etl.mapping.wizard.line'
    _description = 'ETL Mapping Line'
    _order = 'odoo_field'

    wizard_id = fields.Many2one('etl.mapping.wizard', string='Wizard', required=True, ondelete='cascade')

    # Odoo side
    odoo_field = fields.Selection(selection='_get_odoo_fields_selection', string='Odoo Field', required=True)
    odoo_field_type = fields.Char(string='Field Type')
    odoo_field_label = fields.Char(string='Field Label')

    # Mapping configuration
    mapping_type = fields.Selection([
        ('column', 'Direct Column'),
        ('lambda', 'Lambda Function'),
        ('join', 'Join/Lookup'),
    ], string='Mapping Type', required=True, default='column')

    # For column mapping
    legacy_column = fields.Selection(selection='_get_legacy_columns_selection', string='Legacy Column', help='Column in legacy database')

    # For lambda mapping
    lambda_function = fields.Text(string='Lambda Function', help='e.g., lambda self, record, **kwargs: record["id"]')

    # For join mapping
    join_lookup_table = fields.Char(string='Lookup Table', help='e.g., op.course')
    join_left_on = fields.Char(string='Left On (Legacy Column)')
    join_right_on = fields.Char(string='Right On (Odoo Field)')
    join_model_field = fields.Char(string='Model Field (optional)')

    # Optional data type
    data_type = fields.Char(string='Data Type', help='e.g., pl.Int64, pl.Utf8')

    @api.model
    def _get_odoo_fields_selection(self):
        """Get Odoo fields from stored transient records"""
        wizard_id = self._get_wizard_id()
        if wizard_id:
            stored_fields = self.env['etl.mapping.wizard.odoo.field'].search([('wizard_id', '=', wizard_id)])
            return [(f.field_name, f"{f.field_name} ({f.field_label})") for f in stored_fields]
        return [('_dummy_', 'No fields available')]

    @api.model
    def _get_legacy_columns_selection(self):
        """Get legacy columns from stored transient records"""
        wizard_id = self._get_wizard_id()
        if wizard_id:
            stored_columns = self.env['etl.mapping.wizard.legacy.column'].search([('wizard_id', '=', wizard_id)])
            return [(c.column_name, c.column_name) for c in stored_columns]
        return [('_dummy_', 'No columns available')]

    @api.model
    def _get_wizard_id(self):
        """Get wizard_id from multiple sources"""
        # From self (when editing existing line)
        if self and hasattr(self, 'wizard_id') and self.wizard_id:
            return self.wizard_id.id

        # From context (when creating new line)
        if self.env.context.get('default_wizard_id'):
            return self.env.context.get('default_wizard_id')

        # From active context (when form opened from One2many)
        if self.env.context.get('active_model') == 'etl.mapping.wizard' and self.env.context.get('active_id'):
            return self.env.context.get('active_id')

        # Last resort - find most recent wizard
        recent_wizard = self.env['etl.mapping.wizard'].search([], order='id desc', limit=1)
        return recent_wizard.id if recent_wizard else None
