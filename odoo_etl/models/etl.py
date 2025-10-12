from odoo import _, api, fields, models
import time
from datetime import datetime
import logging
import polars as pl
import os
import glob
import gc
import warnings
from collections import Counter, defaultdict

warnings.filterwarnings("ignore", category=pl.exceptions.MapWithoutReturnDtypeWarning)
warnings.filterwarnings("ignore", category=pl.exceptions.PolarsInefficientMapWarning)

_logger = logging.getLogger(__name__)

import psutil, os

def log_memory(tag=""):
    process = psutil.Process(os.getpid())
    mem = process.memory_info().rss / 1024 ** 2
    _logger.debug(f"[MEMORY] {tag} - {mem:.2f} MB")
        
class ETLModel(models.Model):
    _name = 'etl.model'
    _description = 'ETL Model'
    


    name = fields.Char(string='Legacy Table Name', required=True)
    odoo_name = fields.Char(string='Odoo Table Name')
    
    field_mapping = fields.Text('Field Mapping')
    arguments = fields.Text('Arguments')
    
    last_import = fields.Datetime('Last Import')
    last_export = fields.Datetime('Last Export')
    
    elapsed_time_import = fields.Char('Job import Duration (s)')
    elapsed_time_export = fields.Char('Job export Duration (s)')
    
    total_imported_rec = fields.Integer('Total Imported')
    new_imported_rec = fields.Integer('New Imported')
    updated_imported_rec = fields.Integer('Updated Imported')
    
    unique_identifier_tuple = fields.Char('Unique identifier Tuple')
    
    
    remove_condition = fields.Char('Remove Condition') 
    
    
    bulk_import = fields.Boolean('Bulk Import', default = False)
    
    custom_import = fields.Boolean('Custom Import', default = False)
    
    pre_exec = fields.Boolean('Pre Execution', default = False)
    
    dbsource_id = fields.Many2one('base.external.dbsource', string='Database Source', required=True, default=lambda self: self.env['base.external.dbsource'].search([], limit=1))
    
    enabled = fields.Boolean('Job Enabled', default = False)
    
    dry_run = fields.Boolean('Dry Run', default = False, help="If enabled, the import will not create or update any records in Odoo.")
    
    def systematic_import(self):
        return {}

    @api.model_create_multi
    def create(self, vals_list):
        # Normalize to list for uniform processing
        if not isinstance(vals_list, list):
            vals_list = [vals_list]

        # Strip whitespace from string fields
        for vals in vals_list:
            if 'odoo_name' in vals and isinstance(vals['odoo_name'], str):
                vals['odoo_name'] = vals['odoo_name'].strip()
            if 'name' in vals and isinstance(vals['name'], str):
                vals['name'] = vals['name'].strip()

        return super(ETLModel, self).create(vals_list)
    
    
    
    def call_model_import(self):
        self.ensure_one()
        _logger.info(self.name)
        _logger.info("Import record for %s", str(self.name))
        
        try:
            self.odoo_name = self.odoo_name.strip()
            self.import_table_records()
        except Exception as e:
            _logger.error("An error occurred while importing %s", self.name)
            raise e
    
    def call_model_export(self):
        self.ensure_one()
        _logger.info(self.name)
        _logger.info("Export record for %s", str(self.name))

        try:
            self.odoo_name = self.odoo_name.strip()
            self.export_table_records()
        except Exception as e:
            _logger.error("An error occurred while exporting %s: %s", self.name, e)
            raise

    def action_open_mapping_wizard(self):
        """Open the mapping wizard with current ETL model data"""
        self.ensure_one()

        wizard = self.env['etl.mapping.wizard'].create({
            'etl_model_id': self.id,
            'dbsource_id': self.dbsource_id.id,
            'legacy_table_name': self.name,
            'odoo_model_name': self.odoo_name,
            'unique_identifier_tuple': self.unique_identifier_tuple or '',
            'arguments': self.arguments or '',
            'remove_condition': self.remove_condition or '',
            'custom_import': self.custom_import,
            'pre_exec': self.pre_exec,
            'bulk_import': self.bulk_import,
            'dry_run': self.dry_run,
        })

        # Populate transient records for Selection dropdowns BEFORE parsing JSON
        if self.odoo_name and self.odoo_name in self.env:
            odoo_fields = self.env[self.odoo_name].fields_get()
            for field_name, field_info in sorted(odoo_fields.items()):
                self.env['etl.mapping.wizard.odoo.field'].create({
                    'wizard_id': wizard.id,
                    'field_name': field_name,
                    'field_label': field_info.get('string', field_name),
                })

        if self.name and self.dbsource_id:
            try:
                legacy_columns = wizard._get_legacy_table_columns(self.name)
                for column in legacy_columns:
                    self.env['etl.mapping.wizard.legacy.column'].create({
                        'wizard_id': wizard.id,
                        'column_name': column.lower(),
                    })
            except Exception as e:
                _logger.warning("Could not fetch legacy columns: %s", e)

        # Parse existing field mapping and create wizard lines
        if self.field_mapping:
            try:
                import re

                field_mapping_text = self.field_mapping
                field_mapping = eval(field_mapping_text)

                for odoo_field, mapping_config in field_mapping.items():
                    line_vals = {
                        'wizard_id': wizard.id,
                        'odoo_field': odoo_field,
                    }

                    mapping_type = mapping_config.get('type', 'column')
                    line_vals['mapping_type'] = mapping_type

                    if mapping_type == 'column':
                        line_vals['legacy_column'] = mapping_config.get('column_name', '').lower()

                    elif mapping_type == 'lambda':
                        # Extract lambda code from the raw text
                        lambda_str = self._extract_lambda_from_text(field_mapping_text, odoo_field)
                        line_vals['lambda_function'] = lambda_str

                    elif mapping_type == 'join':
                        line_vals['join_lookup_table'] = mapping_config.get('lookup_table', '')
                        line_vals['join_left_on'] = mapping_config.get('left_on', '')
                        line_vals['join_right_on'] = mapping_config.get('right_on', '')
                        line_vals['join_model_field'] = mapping_config.get('model_field', '')

                    if 'data_type' in mapping_config:
                        line_vals['data_type'] = mapping_config.get('data_type', '')
                    print(line_vals)
                    self.env['etl.mapping.wizard.line'].with_context(default_wizard_id=wizard.id).create(line_vals)

                wizard.write({'state': 'map'})

            except Exception as e:
                _logger.error("Error parsing field mapping: %s", e, exc_info=True)
                raise

        return {
            'type': 'ir.actions.act_window',
            'name': 'Edit Field Mapping',
            'res_model': 'etl.mapping.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def _extract_lambda_from_text(self, field_mapping_text, odoo_field):
        """Extract lambda function code from field mapping text"""
        import re

        escaped_field = re.escape(odoo_field)
        func_pattern = rf"'{escaped_field}':\s*\{{[^}}]*'function':\s*(lambda\s)"
        func_match = re.search(func_pattern, field_mapping_text, re.DOTALL)

        if not func_match:
            return "lambda self, record, **kwargs: ..."

        start_pos = func_match.start(1)
        text_from_lambda = field_mapping_text[start_pos:]

        # Balance parentheses/brackets to find lambda end
        depth = 0
        in_string = False
        string_char = None
        end_pos = 0

        for i, char in enumerate(text_from_lambda):
            if char in ['"', "'"]:
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char and (i == 0 or text_from_lambda[i-1] != '\\'):
                    in_string = False
                    string_char = None
                continue

            if in_string:
                continue

            if char in '([{':
                depth += 1
            elif char in ')]}':
                depth -= 1

            if depth == 0 and i > 10:
                remaining = text_from_lambda[i:i+5]
                if re.match(r',\s*[\'"}]', remaining) or re.match(r'\s*}', remaining):
                    end_pos = i
                    break

        if end_pos > 0:
            return text_from_lambda[:end_pos].strip().rstrip(',').strip()

        return "lambda self, record, **kwargs: ..."
            
    def import_table_records(self,**kwargs):
        if not self.odoo_name or not self.name:
            _logger.info("Model not found")
            raise 
        _logger.info("Start import odoo table: %s and external table: %s (source: %s)", self.odoo_name, self.name, self.dbsource_id.name)

        start = time.time()

        
        kwargs = self.systematic_import()
        

        total_records, new_records, updated_records = 0, 0, 0
        last_import_time = fields.Datetime.now()
        
        if self.pre_exec == True: 
            _logger.info("Sart pre_exec for '%s'  and legacy %s", self.odoo_name, self.name)
            self.env[self.odoo_name].pre_exec(**kwargs)
            _logger.info("End pre_exec for '%s'  and legacy %s", self.odoo_name, self.name)
        if self.custom_import == True:
            _logger.info("Sart custom_import for '%s'  and legacy %s", self.odoo_name, self.name)
            self.env[self.odoo_name].custom_import(**kwargs)
            _logger.info("End custom_import for '%s'  and legacy %s", self.odoo_name, self.name)
        else:      
            try:     
                data = self.execute_query("SELECT * FROM " + self.name.strip() + ";", (), metadata=True)
            except Exception as e:
                _logger.error("An error occurred, make sure you have imported the ETL models: %s", str(e))
                raise e
            data.columns = [col.lower() for col in data.columns]

        

            field_mapping = eval(self.field_mapping)

            unique_identifier_tuple = eval(self.unique_identifier_tuple)

            if self.remove_condition:
                data = data.filter(eval(self.remove_condition)).clone()


            
            if self.arguments :
                for option in self.arguments.split("|"):
                    try:
                        key, value = option.strip().split(" = ")
                    except ValueError:
                        _logger.error("An error occurred while parsing argument '%s' of %s", option, self.name)
                    except SyntaxError:
                        _logger.error("A syntax error occurred while evaluating argument '%s' for %s", option, self.name)
                    except Exception as e:
                        _logger.error("An unexpected error occurred: %s", str(e))
                        raise e
                    kwargs[key.strip()] = eval(value)

            _logger.info("Model %s is using the following arguments %s", self, str(kwargs) )
            
            kwargs['start_time'] = start
            
            total_records, new_records, updated_records = self.import_records(data, unique_identifier_tuple, field_mapping, **kwargs)
            

        end = time.time()
        
        duration = end-start
        
        self.write({
                'elapsed_time_import': duration,
                'last_import': last_import_time,
                'total_imported_rec': total_records,
                'new_imported_rec': new_records,
                'updated_imported_rec': updated_records,
            })

        _logger.info("Total time= %s seconds for %s records", duration, str(total_records) )    
        self.env.cr.commit()
        
    @api.model
    def get_schema(self):
        schema = {}
        field_mapping = eval(self.field_mapping)
        for name, options in field_mapping.items():
            for key, option in options.items():
                schema[name] = option if key == 'data_type' else None
        return schema
    @api.model
    def get_sqlite_column_types(self, dbsource):
        data = dbsource.execute_sqlite(f"PRAGMA table_info({self.name});", (), metadata=False)[0]
        utils = self.env['polars.sql.type.mapper']
        column_types = {row[1]: utils._get_polars_type(row[2]) for row in data}
        return column_types
        
    @api.model
    def execute_query(self, sql_query, sql_params, metadata=True, sqlite_guess=True):
        
        dbsource = self.dbsource_id
        if not dbsource:
            raise ValueError("Database source not defined.")
            
        """Fetches all records from the adequate table."""
        try:
            offset = 0
            all_batches = []
            batch_size = 25000
            while True:
                # Modify SQL query to support batching with OFFSET and LIMIT
                if 'select' in sql_query.lower().split()[0]:
                    adapted_sql = f"{sql_query.replace(';', '')} LIMIT {batch_size} OFFSET {offset};"
                else:
                    adapted_sql = sql_query
                # Execute the SQL query
                data, cols = dbsource.execute_sqlite(adapted_sql, sql_params, metadata)

                # Break the loop if no more records are found
                if not data:
                    break
                
                if metadata:
                    # Process batch into Polars DataFrame
                    datarray = [list(tuple_item) for tuple_item in data]

                    if sqlite_guess:
                        schema = self.get_sqlite_column_types(dbsource)

                        batch_df = pl.DataFrame(datarray, schema=schema, orient="row", infer_schema_length=batch_size)
                    else:
                        batch_df = pl.DataFrame(datarray, schema=cols, orient="row", infer_schema_length=batch_size)
                    all_batches.append(batch_df)

                # Move to the next batch
                offset += batch_size

            # Fix columns with Null dtype across all_batches
            if metadata and all_batches:
                for col_idx, col_name in enumerate(all_batches[0].columns):
                    if all_batches[0].dtypes[col_idx] == pl.Null:
                        for other_batch in all_batches:
                            if col_name in other_batch.columns and other_batch.dtypes[col_idx] != pl.Null:
                                target_dtype = other_batch.dtypes[col_idx]
                                for i, batch in enumerate(all_batches):
                                    all_batches[i] = batch.with_columns(
                                        pl.col(col_name).cast(target_dtype)
                                    )
                                break

            # Concatenate all batches into a single DataFrame
            if metadata:
                if len(all_batches) == 0:
                    raise ValueError(f"{self.name}:{self.odoo_name} might be empty ")
                final_df = pl.concat(all_batches, how="vertical_relaxed")
                return final_df
            else:
                return

        except Exception as e:
            _logger.error("An error occurred while fetching %s", sql_query)
            raise e
        
    @api.model
    def load_records_in_batches(self, odoo_name, odoo_columns, batch_size=5000, **kwargs):
        """
        Load records in batches of a specified size and process them.
        
        Args:
            self: Odoo environment object.
            odoo_name: The name of the Odoo model.
            odoo_columns: List of columns to fetch from the model.
            batch_size: Number of records to fetch per batch.

        Returns:
            Polars DataFrame containing all records.
        """
        offset = 0          # Initialize offset
        
        fields_info = self.env[odoo_name].fields_get(odoo_columns)
        boolean_fields = [field for field, info in fields_info.items() if info['type'] == 'boolean']
        tuple_fields = [field for field, info in fields_info.items() if info['type'] == 'many2many']
        int_fields = [field for field, info in fields_info.items() if info['type'] == 'integer'] 
        many2one_fields = [field for field, info in fields_info.items() if info['type'] == 'many2one'] 
        date_fields = [field for field, info in fields_info.items() if info['type'] == 'date']         
        
        dtype_counts = defaultdict(Counter)
        
        while True:
            # Fetch records in batches using offset and limit
            log_memory(f"Loading batch with offset {offset}")
            current_data_records = self.env[odoo_name].search_read([], odoo_columns, offset=offset, limit=batch_size, order='id')
            
            # Break loop if no more records are found
            if not current_data_records:
                break

            # Process the first record to identify tuple fields
            first_record = current_data_records[0]
            tuple_fields = [key for key, value in first_record.items() if isinstance(value, tuple)]

            # Process records to replace False values in tuple fields with None
            for record in current_data_records:
                for field in tuple_fields + many2one_fields + date_fields:
                    if record[field] is False:
                        record[field] = None

            # Convert the batch into a Polars DataFrame
            
            batch_df = pl.DataFrame(current_data_records, strict=False, infer_schema_length=batch_size)
            for col, dtype in zip(batch_df.columns, batch_df.dtypes):
                dtype_counts[col][dtype] += 1
            batch_df.write_parquet(f"/tmp/batch_{offset}.parquet")
            # Move to the next batch
            offset += batch_size

            self.env.clear()


        placeholder_types = [pl.Boolean, pl.Null, pl.Unknown]

        final_dtypes = {}
        for col, counter in dtype_counts.items():
            # Start with the most common type
            most_common_type, _ = counter.most_common(1)[0]
            # If it's a placeholder type, try to find a "real" type
            if most_common_type in placeholder_types:
                
                for dtype in counter:
                    if dtype not in placeholder_types:
                        most_common_type = dtype
                        break

            final_dtypes[col] = most_common_type
            
        print(final_dtypes)
        path = "/tmp/batch_*.parquet"
        for file in glob.glob(path):
            df = pl.read_parquet(file)
            # repaint columns with final_dtypes
            for col, dtype in final_dtypes.items():
                if col in df.columns:
                    if col in date_fields:
                   
                        df = df.with_columns(
                            pl.when(pl.col(col).is_null())
                            .then(None)
                            .otherwise(pl.col(col))
                            .cast(pl.Date)
                            .alias(col)
                        )
                    else:
                        df = df.with_columns(pl.col(col).cast(dtype))
            # overwrite the parquet file with fixed schema
            df.write_parquet(file)

        gc.collect()
        self.env.clear()

        
        files = glob.glob(path)

        if files:  # ✅ at least one parquet file exists
            final_df = pl.scan_parquet(path, allow_missing_columns=True).collect(streaming=True)
            # cleanup
        else:
            # no parquet files → empty dataframe
            final_df = pl.DataFrame()
        for file in files:
            os.remove(file)
        log_memory("Concatenating all batches")
        return final_df
    
    @api.model
    def import_records(self, data, unique_identifier_tuple, field_mapping, **kwargs):
        """
        Generic function to import records into any Odoo model.

        :param data: A Polars DataFrame containing the data to import.
        :param unique_identifier_tuple: The field name tuple used to check if the record already exists with format : 
                                        (odoo_table_index, legacy_table_index) or 
                                        (odoo_table_index, (legacy_table_index_1, legacy_table_index_2, ...)).
        :param field_mapping: A dictionary mapping Odoo field names to DataFrame column names.
        :param kwargs: It is a dict of potential new arguments that can be added and used by the field_mapping.
        """

        # Unpack the unique identifier tuple
        odoo_unique_identifier, unique_identifier = unique_identifier_tuple

        # Check if unique_identifier is a tuple
        if isinstance(unique_identifier, tuple):
            # Concatenate the columns corresponding to the legacy indexes
            data = data.with_columns(
                pl.concat_str(data[list(unique_identifier)], separator='-').alias('external_id')
            )
            unique_identifier = 'external_id'

        df = data.select([pl.col(unique_identifier)])
        odoo_columns = []

        for odoo_field, mapping in field_mapping.items():
            odoo_columns.append(odoo_field)
            _logger.info(f"Mapping type for field '{odoo_field}': {mapping}")
            if mapping['type'] == 'column':
                # If it's a string, we assume it's a direct mapping to a DataFrame column
                if mapping['column_name'] in data.columns:
                    if "data_type" in mapping:
                        df = df.with_columns(data[mapping['column_name']].cast(eval(mapping['data_type'])).alias(odoo_field))
                    else :
                        df = df.with_columns(data[mapping['column_name']].alias(odoo_field))
                else:
                    raise ValueError(f"Column '{mapping}' not found in the data.")
            elif mapping['type'] == 'lambda':
                df = df.with_columns(
                        data.select([
                            pl.struct(pl.all()).map_elements(
                                lambda row: mapping['function'](self, row, **kwargs),  # The mapping function
                            ).alias(odoo_field)  # Alias for the new column
                        ]).to_series())
                
                if "data_type" in mapping:
                    if mapping['data_type'] == 'pl.Datetime':
                        df = df.with_columns(
                                pl.col(odoo_field).str.to_datetime("%Y-%m-%d %H:%M:%S"))
                    else :
                        df = df.with_columns(
                                pl.col(odoo_field).cast(eval(mapping['data_type'])))
                    
            elif mapping['type'] == 'object_lambda':
                df = df.with_columns(
                        data.select([
                            pl.struct(pl.all()).map_elements(
                                lambda row: mapping['function'](self, row, **kwargs),  # The mapping function
                                return_dtype=pl.Object
                            ).alias(odoo_field)  # Alias for the new column
                        ]).to_series()
                    )
            elif mapping['type'] == 'join':
                domain = mapping.get('filter') or []
                lookup_data = self.env[mapping['lookup_table']].search(domain)
                right_on = mapping['right_on']
                left_on = mapping['left_on']
                
                join_colum_name = 'join_column_odoo'
                lookup_colum_name = 'lookup_colum_name'
                new_column_name = 'new_column_name'
                
                lookup_table = pl.DataFrame([{
                                    join_colum_name: getattr(rec, right_on),
                                    lookup_colum_name:  getattr(rec, mapping['model_field']).id if "model_field" in mapping else rec.id
                                } for rec in lookup_data])
                

                data_copy = data.select(left_on).clone().rename({left_on : new_column_name})
                df = df.with_columns(data_copy.select(new_column_name))

                if "data_type" in mapping:
                    df = df.with_columns(
                            pl.col(new_column_name).cast(eval(mapping['data_type']))
                        )
                df = df.join(
                        lookup_table, 
                        left_on=new_column_name, 
                        right_on=join_colum_name, 
                        how="left"
                    ).with_columns(pl.col(lookup_colum_name).alias(odoo_field)).drop([new_column_name, lookup_colum_name])

                
                if 'filter_right' in mapping:
                    df = df.filter(pl.col(odoo_field).is_not_null())

            elif mapping['type'] == 'user_group':
                pass
                
            else:
                _logger.error(f"Unsupported mapping type for field '{odoo_field}': {type(mapping)}")    
                
        # TODO use the existing_df as input in the filtered df to now call load_records_in_batches twice  
        filtered_df = self.hash_compare(df.clone(), odoo_columns, unique_identifier, odoo_unique_identifier, **kwargs)
        _logger.info(filtered_df)


        existing_df = self.load_records_in_batches( self.odoo_name, [odoo_unique_identifier, 'id'], batch_size=5000, **kwargs)
        log_memory(f"Existing df")
        if existing_df.is_empty():
            records_to_create = filtered_df
            records_to_update = pl.DataFrame()
            
        else:
            if unique_identifier == "id":
                filtered_df = filtered_df.rename({"id": "id_left"})
                unique_identifier = "id_left"

            existing_df = existing_df.with_columns(
                pl.col(odoo_unique_identifier).cast(filtered_df.schema[unique_identifier]).alias(odoo_unique_identifier)
            )
            merged = filtered_df.join(
                existing_df,
                left_on=unique_identifier,
                right_on=odoo_unique_identifier,
                how="left"
            )
            new_records = merged.filter(pl.col("id").is_null())
            existing_records = merged.filter(pl.col("id").is_not_null())
            records_to_create = new_records.drop("id")
            records_to_update = existing_records
            
        drop_unique_id = unique_identifier not in self.env[self.odoo_name].fields_get() 
        if drop_unique_id:
            records_to_create = records_to_create.drop(unique_identifier, strict=False)
            records_to_update = records_to_update.drop(unique_identifier, strict=False)
        
        _logger.info("Time to prepare data= %s seconds", time.time() - kwargs['start_time'])
        
        if self.dry_run:
            _logger.info("Dry run enabled, skipping actual import.")
            return len(filtered_df), 0, 0
        
        _logger.info("Start ORM Import")

        failed_create = 0
        failed_update = 0
        max_errors = 400
        if self.bulk_import and len(records_to_create) > 0:
            error_records = self.create_records_in_batch(records_to_create)
            for record in error_records.iter_rows(named=True):
                success = self.create_record(record)
                if not success:
                    failed_create += 1
                if failed_create >= max_errors:
                    _logger.error("Max errors reached, stopping import")
                    break
        else:
            for record in records_to_create.iter_rows(named=True):
                success = self.create_record(record)
                if not success:
                    failed_create += 1
                if failed_create >= max_errors:
                    _logger.error("Max errors reached, stopping import")
                    break

        for row in records_to_update.iter_rows(named=True):
            record_id = row['id']
            values = {k: v for k, v in row.items() if k != 'id'}
            if not self.update_record(record_id, values):
                failed_update += 1

        return len(df), len(records_to_create) - failed_create, len(records_to_update) - failed_update

    def create_record(self, record):
        try:
            with self.env.cr.savepoint():
                self.env[self.odoo_name].with_context(tracking_disable=True, mail_notrack=True).create(record)
                
        except Exception as ex:
            _logger.error(f"Error details create: {ex}")

            return False  # Reduce exception count
        return True  # Creation successful, no reduction in exceptions

    # Function to handle batch record creation
    def create_records_in_batch(self, records: pl.DataFrame, batch_size: int = 5000):
        errored_batches = []

        num_rows = records.height
        for start in range(0, num_rows, batch_size):
            _logger.info(f"Creating records from {start} to {start + batch_size}")
            end = min(start + batch_size, num_rows)
            batch_df = records.slice(start, end - start)

            try:
                with self.env.cr.savepoint():
                    self.env[self.odoo_name].with_context(tracking_disable=True, mail_notrack=True).create(batch_df.to_dicts())
            except Exception as ex:
                _logger.error(f"Batch creation failed for rows {start} to {end}")
                _logger.error(f"Error details batch create: {ex}")
                errored_batches.append(batch_df)

        if errored_batches:
            error_df = pl.concat(errored_batches)
            return error_df
        else:
            return pl.DataFrame()



    # Function to handle individual record updates with error tracking
    def update_record(self, record_id, values):
        try:
            with self.env.cr.savepoint():
                self.env[self.odoo_name].browse(record_id).with_context(tracking_disable=True, mail_notrack=True).write(values)

        except Exception as ex:
            _logger.error(f"Error details update: {ex}")

            return False
        return True

    def odoo_to_polars(self, odoo_df, col):
        odoo_to_polars_type_map = {
            'integer': pl.Int64,
            'float': pl.Float64,
            'char': pl.Utf8,
            'text': pl.Utf8,
            'boolean': pl.Boolean,
            'datetime': pl.Datetime,
            'date': pl.Date,
            'many2one': pl.Int64,  
        }
        
        field_info = self.env[self.odoo_name].fields_get([col])
        field_type = field_info[col]['type']
        if field_type not in ['boolean', 'selection']:
            odoo_df = odoo_df.with_columns(
                        pl.col(col).cast(odoo_to_polars_type_map[field_type]).alias(col)
                    )
        return odoo_df
   
    def remove_false(self,df):
        return df.with_columns(pl.col(pl.String).replace("false", None))
             
    def hash_compare(self, dataframe, odoo_columns, unique_identifier, odoo_unique_identifier, **kwargs):

        current_data_df = self.load_records_in_batches(self.odoo_name, odoo_columns, **kwargs)

        if current_data_df.is_empty():
            return dataframe
        
        # serch_read return "false" for null value in sql, this fixes it.
        current_data_df = self.remove_false(current_data_df)
        
        # Polars insert null value that are interpreted by 0 in odoo when record is created 
        dataframe = dataframe.with_columns(pl.col(pl.Int64).replace(None, False))
        
        # Check if current_data_df or dataframe are empty
        if current_data_df.is_empty() or dataframe.is_empty():
            # If either is empty, skip hashing and filtering
            _logger.warning("No records to compare or DataFrame is empty.")
            return dataframe
        else:
            # Set the object colmun in order to make sure to be able to use them
            object_column = []
            if any( dtype == pl.Object for dtype in dataframe.dtypes):
                def format_list_to_object(lst):
                    return [(6, 0, lst.to_list())]
                
                object_column = dataframe.select(pl.col(pl.Object)).columns[0]
                current_data_df = current_data_df.with_columns(
                    pl.col(object_column)
                    .map_elements(format_list_to_object, return_dtype=pl.Object)
                )    
            
            if unique_identifier == 'id':
                current_data_df = current_data_df.rename({odoo_unique_identifier : 'unique_identifier'})
                dataframe = dataframe.rename({unique_identifier : 'unique_identifier'})
                odoo_columns[odoo_columns.index(odoo_unique_identifier)] = 'unique_identifier'
                unique_identifier = 'unique_identifier'
                odoo_columns = [unique_identifier if w == odoo_unique_identifier else w for w in odoo_columns]

            else:
                if current_data_df[odoo_unique_identifier].dtype == pl.Boolean:
                    current_data_df = self.odoo_to_polars(current_data_df, odoo_unique_identifier)
                current_data_df = current_data_df.rename({odoo_unique_identifier : unique_identifier})
                odoo_columns = [unique_identifier if w == odoo_unique_identifier else w for w in odoo_columns]
            
            
            for col in odoo_columns:
                # Handle tuple fields like 'course_id' by extracting the ID if it's a tuple ["53", "FRANCAIS DE BASE -  AT…"]
                if current_data_df[col].dtype == pl.List:
                    current_data_df = current_data_df.with_columns(
                        pl.col(col).map_elements(lambda x: x[0] if (x is not None and len(x) > 1) else None, skip_nulls=False).cast(pl.Int64).alias(col)
                    )
                # Handle the case where the dataframe is set to bolean and should not
                if current_data_df[col].dtype == pl.Boolean:
                    current_data_df = self.odoo_to_polars(current_data_df, col)
                if col in dataframe.columns and col in current_data_df.columns:
                    try:
                        dataframe = dataframe.with_columns(pl.col(col).cast(current_data_df[col].dtype))
                    except Exception as e:
                        _logger.warning(f"Data type alignment issue on column {col}: {e}")
                        return dataframe      
                    
            def sort_exisiting_list(lst):
                    return str([(6, 0, sorted(lst))])
            # Helper function to add a hashed 'record_hash' column to a DataFrame
            def add_record_hash(df, columns, object_column, seed=42):   
                if object_column:
                    df = df.with_columns(pl.col(object_column).map_elements(lambda x: sort_exisiting_list(x[0][2])))
                
                hash_df = df.with_columns(
                    [pl.col(col).fill_null(strategy="zero") for col in columns]
                )
                
                hash_df = hash_df.with_columns(
                    pl.concat_str(columns, separator="-")  # Concatenate columns as strings
                    .hash(seed=seed)                       # Apply hash with a seed
                    .cast(pl.Utf8)                         # Convert hash to a string
                    .alias("record_hash")                  # Name the new column
                )
                
                return df.with_columns(hash_df["record_hash"])
            
            # Apply the function to add 'record_hash' to both DataFrames
            current_data_df = add_record_hash(current_data_df, odoo_columns, object_column)

            dataframe = add_record_hash(dataframe, odoo_columns, object_column)
            
            # Check if each hash in dataframe exists in current_data_df
            dataframe2 = dataframe.with_columns(
                (pl.col('record_hash').is_in(current_data_df['record_hash'])).alias('exists_in_odoo')
            )

            df_filtered = dataframe2.filter(pl.col('exists_in_odoo') == False).clone()
            


            

            # Drop the auxiliary columns used for hashing if they are no longer needed
            df_filtered = df_filtered.drop(['record_hash', 'exists_in_odoo'])

            # If object_colmun, make sure to convert it back so that it can be used by odoo
            if object_column:
                df_filtered = df_filtered.with_columns(pl.col(object_column).map_elements(lambda x: eval(x), return_dtype=pl.Object))
               
            if unique_identifier == 'unique_identifier':
                df_filtered = df_filtered.rename({'unique_identifier' : 'id'})
            return df_filtered
        
    
    def export_table_records(self):
        pass
    

            
    def import_model(self, odoo_name=None, name=None, dbsource_id=None, **kwargs):
        """Helper function to search and import records."""
        domain = []
        if odoo_name:
            self.odoo_name = odoo_name.strip()
            domain.append(("odoo_name", "=", odoo_name))
        if name:
            self.name = name.strip()
            domain.append(("name", "=", name))
        if dbsource_id:
            domain.append(('dbsource_id', '=', dbsource_id))
        model = self.env["etl.model"].search(domain, limit=1)
        if model:
            model.import_table_records(**kwargs)

    