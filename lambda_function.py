""" ONLY FOR DEVELOPMENT REMOVE ON LAMBDA """
from dotenv import load_dotenv, dotenv_values 
load_dotenv()
""" IMPORTS """
import boto3
import json
import os
from typing import List, Dict, Any, Optional, Union
from botocore.exceptions import ClientError
from datetime import datetime, timedelta, date

""" GLOBAL VARIABLES """
SUCCESS         = "🟢"  # Green dot
FAIL            = "🟡"  # yellow dot
ERROR           = "🔴"  # Warning sign

DB_NAME         = os.environ.get("DB_NAME")
ARN_AURORA      = os.environ.get("AURORA_CLUSTER_ARN")
ARN_SECRET      = os.environ.get("AURORA_SECRET_ARN")
ARN_SQS         = os.environ.get("SQS_QUEUE_ARN")
REGION          = os.environ.get("REGION")

AWS_TYPECASTS   =   {
                        'created_at': 'timestamp with time zone',
                        'updated_at': 'timestamp with time zone',
                        'joined_timestamp': 'timestamp with time zone',
                        'period_start': 'timestamp with time zone',
                        'date_from': 'timestamp with time zone',
                        'date_to': 'timestamp with time zone',
                        'period_end': 'timestamp with time zone',
                        'service_id': 'int',
                        'security_id': 'int',
                        'period_granularity': 'period_granularity_type',
                    }

AWS_TYPECAST_2  =   {
                        'timestamp'                 :   [
                                                            'created_at',
                                                            'updated_at',
                                                            'joined_timestamp',
                                                            'period_start',
                                                            'period_end',
                                                            'date_from',
                                                            'date_to'
                                                        ],
                        'period_granularity_type'   :   [
                                                            'period_granularity'
                                                        ],
                        'varchar_array'             :   [
                                                            'usage_types'
                                                        ],
                        'numeric'                   :   [
                                                            'cost',
                                                            'utilization',
                                                            'current_period_cost',
                                                            'previous_period_cost',
                                                            'cost_difference',
                                                            'cost_difference_percentage',
                                                            'potential_monthly_savings',
                                                            'amount',
                                                            'prediction_interval_lower_bound',
                                                            'prediction_interval_upper_bound'
                                                        ],
                    }

TYPE_CASTING    =   {
                        'timestamp with time zone'  : AWS_TYPECAST_2['timestamp'],
                        'period_granularity_type'   : AWS_TYPECAST_2['period_granularity_type'],
                        'varchar[]'                 : AWS_TYPECAST_2['varchar_array'],
                        'numeric'                   : AWS_TYPECAST_2['numeric']
                    }

""" HELPER CLASSES """

""" 1. SQS MANAGER """
class SQSManager:
    def __init__(self, queue_arn: str):
        """
        Initialize SQS wrapper with queue ARN
        Args:
            queue_arn (str): The ARN of the queue
        """
        self.queue_arn = queue_arn
        self.region = queue_arn.split(':')[3]
        self.account_id = queue_arn.split(':')[4]
        self.queue_name = queue_arn.split(':')[-1]
        self.sqs = boto3.client('sqs', region_name=self.region)
        self.queue_url = self._get_queue_url()

    def _get_queue_url(self) -> str:
        """
        Get queue URL from ARN
        Returns:
            str: Queue URL
        """
        try:
            response = self.sqs.get_queue_url(
                QueueName=self.queue_name,
                QueueOwnerAWSAccountId=self.account_id
            )
            return response['QueueUrl']
        except ClientError as e:
            print(f"Error getting queue URL: {e}")
            raise

    def _generate_deduplication_id(self, message: Union[str, Dict]) -> str:
        """
        Kept for compatibility, not used in standard queues
        """
        return ""

    def send_message(self,
                    message: Union[str, Dict],
                    message_group_id: str = None,  # Kept for compatibility
                    message_deduplication_id: str = None,  # Kept for compatibility
                    message_attributes: Dict = None,
                    delay_seconds: int = 0) -> Optional[Dict]:
        """
        Send a message to the queue
        Args:
            message (Union[str, Dict]): Message content
            message_attributes (Dict): Optional message attributes
            delay_seconds (int): Delay delivery of message
        Returns:
            Optional[Dict]: Message send result
        """
        try:
            if isinstance(message, dict):
                message = json.dumps(message)

            params = {
                'QueueUrl': self.queue_url,
                'MessageBody': message,
                'DelaySeconds': delay_seconds
            }

            if message_attributes:
                params['MessageAttributes'] = message_attributes

            response = self.sqs.send_message(**params)
            return response
        except ClientError as e:
            print(f"Error sending message: {e}")
            return None

    def receive_messages(self,
                        message_group_id: str = None,  # Kept for compatibility
                        max_messages: int = 10,
                        wait_time_seconds: int = 0,
                        visibility_timeout: int = 50,
                        message_attributes: List[str] = None) -> List[Dict]:
        """
        Receive messages from the queue
        Args:
            max_messages (int): Maximum number of messages to receive (1-10)
            wait_time_seconds (int): Long polling wait time
            visibility_timeout (int): Visibility timeout in seconds
            message_attributes (List[str]): List of message attribute names to receive
        Returns:
            List[Dict]: List of received messages
        """
        try:
            params = {
                'QueueUrl': self.queue_url,
                'MaxNumberOfMessages': min(max_messages, 10),
                'WaitTimeSeconds': wait_time_seconds,
                'VisibilityTimeout': visibility_timeout,
                'AttributeNames': ['All']
            }

            if message_attributes:
                params['MessageAttributeNames'] = message_attributes
            else:
                params['MessageAttributeNames'] = ['All']

            response    = self.sqs.receive_message(**params)

            return response.get('Messages', [])
        except ClientError as e:
            print(f"Error receiving messages: {e}")
            return []

    def send_message_batch(self, messages: List[Dict]) -> Dict[str, List]:
        """
        Send multiple messages in a batch
        Args:
            messages (List[Dict]): List of messages with required format
                Each message must contain:
                - body: message content
                Optional:
                - delay_seconds: delay in seconds
                - message_attributes: message attributes
        Returns:
            Dict[str, List]: Successful and failed message IDs
        """
        try:
            entries = []
            for i, msg in enumerate(messages):
                entry = {
                    'Id': str(i),
                    'MessageBody': (json.dumps(msg['body'])
                                  if isinstance(msg['body'], dict)
                                  else msg['body'])
                }

                if 'delay_seconds' in msg:
                    entry['DelaySeconds'] = msg['delay_seconds']
                if 'message_attributes' in msg:
                    entry['MessageAttributes'] = msg['message_attributes']

                entries.append(entry)

            response = self.sqs.send_message_batch(
                QueueUrl=self.queue_url,
                Entries=entries
            )

            successful = [msg['Id'] for msg in response.get('Successful', [])]
            failed = [msg['Id'] for msg in response.get('Failed', [])]

            return {
                'successful': successful,
                'failed': failed
            }
        except ClientError as e:
            print(f"Error sending message batch: {e}")
            return {'successful': [], 'failed': [str(i) for i in range(len(messages))]}

    def delete_message(self, receipt_handle: str) -> bool:
        """
        Delete a specific message from the queue using its receipt handle
        Args:
            receipt_handle (str): Receipt handle of the message to delete
        Returns:
            bool: Success status
        """
        try:
            self.sqs.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle
            )
            return True
        except ClientError as e:
            print(f"Error deleting message: {e}")
            return False

    def purge_queue(self) -> bool:
        """
        Purge all messages from the queue
        Note: Can only be called once every 60 seconds
        Returns:
            bool: Success status
        """
        try:
            self.sqs.purge_queue(QueueUrl=self.queue_url)
            print("Queue purged successfully")
            return True
        except ClientError as e:
            if 'AWS.SimpleQueueService.PurgeQueueInProgress' in str(e):
                print("Purge already in progress. Please wait 60 seconds before retrying.")
            else:
                print(f"Error purging queue: {e}")
            return False

""" 2. TEST AWS SERVICES MANAGER """
class TestAwsServices:
    def __init__(self, params=None):
        # Get current date and 30 days ago for CE
        self.end_date           = datetime.now()
        self.start_date         = self.end_date - timedelta(days=30)
        self.obs360_services    = {
                                    'sts'                : {
                                                            'name'      : 'STS',
                                                            'client'    : boto3.client('sts'),
                                                            'action'    : 'get_caller_identity',
                                                            'params'    : params,
                                                            'status'    : False,
                                                        },
                                    'account'            : {
                                                            'name'      : 'Account',
                                                            'client'    : boto3.client('account'),
                                                            'action'    : 'get_contact_information',
                                                            'params'    : params,
                                                            'status'    : False
                                                        },
                                    'sqs'                : {
                                                            'name'      : 'SQS',
                                                            'client'    : boto3.client('sqs', region_name=REGION),
                                                            'action'    : 'list_queues',
                                                            'params'    : params,
                                                            'status'    : False
                                                        },
                                    'rds-data'           : {
                                                            'name'      : 'Aurora RDS',
                                                            'client'    : boto3.client('rds-data'),
                                                            'action'    : 'close',
                                                            'params'    : params
                                                        }
                                }

    def _run_test(self, service):
        try:
            if service['params']:
                service['client'].__getattribute__(service['action'])(**service['params'])
            else:
                service['client'].__getattribute__(service['action'])()
            service['status'] = True
            print(f"{SUCCESS} Connected to {service['name']}")
        except ClientError as e:
            print(f"{FAIL} Not Connected to {service['name']}: {str(e)}")
            service['status'] = False
        except Exception as e:
            print(f"{ERROR} Error testing {service['name']}: {str(e)}")
            service['status'] = None



    def test_obs_360_connection(self):
        print("Testing Database and Other connections")
        print("*"*40)

        passed  = 0
        failed  = 0
        counter = 0

        for key, val in self.obs360_services.items():
            self._run_test(val)

            if val['status'] == True:
                passed += 1
            elif val['status'] == False:
                failed += 1

            counter += 1

        error = counter - (passed + failed)

        print(f"\n\033[92m{passed} Connected\033[0m \n\033[93m{failed} Not Connected\033[0m \n\033[91m{error} Has Errors\033[0m\n")

        if(failed > 0):
            return False
        else:
            return True

""" 3. DB MANAGER """
class DBManager:
    def __init__(self, database_name: str, cluster_arn: None, secret_arn: None):
        """
        Initialize the DBManager with database configuration
        """
        self.database       = database_name
        self.client         = boto3.client('rds-data')
        self.cluster_arn    = cluster_arn if(cluster_arn) else os.environ.get('AURORA_CLUSTER_ARN')
        self.secret_arn     = secret_arn if(secret_arn) else os.environ.get('AURORA_SECRET_ARN')

        if not self.cluster_arn or not self.secret_arn:
            raise ValueError("Missing required environment variables: AURORA_CLUSTER_ARN or AURORA_SECRET_ARN")

    def _format_parameters(self, params: Dict[str, Any]) -> List[Dict]:
        """
        Format parameters for Data API
        """
        formatted_params = []
        for key, value in params.items():
            param = {'name': key}

            if isinstance(value, int):
                param['value'] = {'longValue': value}
            elif isinstance(value, float):
                param['value'] = {'doubleValue': value}
            elif isinstance(value, bool):
                param['value'] = {'booleanValue': value}
            elif isinstance(value, datetime):
                param['value'] = {'stringValue': value.isoformat()}
            elif value is None:
                param['value'] = {'isNull': True}
            else:
                param['value'] = {'stringValue': str(value)}

            formatted_params.append(param)

        return formatted_params

    def _extract_column_names(self, query: str) -> List[str]:
        """
        Extract column names from a SELECT query
        """
        try:
            # Find the SELECT and FROM parts of the query
            select_part = query.lower().split('from')[0].replace('select', '').strip()

            # Split the columns and clean them up
            columns = []
            for col in select_part.split(','):
                col = col.strip()

                # Handle case when column has AS alias
                if ' as ' in col.lower():
                    columns.append(col.split(' as ')[-1].strip())
                # Handle case when column has table prefix
                elif '.' in col:
                    columns.append(col.split('.')[-1].strip())
                # Handle case when column is a function
                elif '(' in col and ')' in col:
                    if ' as ' in col.lower():
                        columns.append(col.split(' as ')[-1].strip())
                    else:
                        columns.append(col.strip())
                else:
                    columns.append(col.strip())

            return columns
        except Exception as e:
            print(f"Error extracting column names: {str(e)}")
            return []

    """ def _format_results(self, response, column_names, results=[]):
        result = {}

        for record in response['records']:
                # Create dictionary with column names and values
                result = {}
                for i, value in enumerate(record):
                    # Extract the actual value from the dictionary
                    actual_value = None
                    if value:
                        # Get the first non-null value from the dictionary
                        for val_type in value.values():
                            if val_type is not None:
                                actual_value = val_type
                                break

                    result[column_names[i]] = actual_value

                results.append(result)

        return results """
    def _format_results(self, response: Dict, column_names: List[str], single_result: bool = False) -> Union[List[Dict], Optional[Dict]]:
        """
        Format query results
        Args:
            response (Dict): Database response
            column_names (List[str]): List of column names
            single_result (bool): If True, return single record instead of list
        Returns:
            Union[List[Dict], Optional[Dict]]: Formatted results as list or single record
        """
        if not response or 'records' not in response or not response['records']:
            return None if single_result else []

        results = []
        for record in response['records']:
            result = {}
            for i, value in enumerate(record):
                # Extract the actual value from the dictionary
                actual_value = None
                if value:
                    # Get the first non-null value from the dictionary
                    for val_type in value.values():
                        if val_type is not None:
                            actual_value = val_type
                            break

                result[column_names[i]] = actual_value

            results.append(result)

        return results[0] if single_result and results else results

    def select_one(self, query: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Execute SELECT query and return single row
        Args:
            query (str): SQL query
            params (Dict, optional): Query parameters
        Returns:
            Optional[Dict]: Single record or None
        """
        try:
            typed_query = self._generate_typed_query(query, params) if params else query
            response    = self.execute_statement(typed_query, params if params else {})

            # Get column names using existing method
            column_names = self._extract_column_names(query)
            result       = self._format_results(response=response, column_names=column_names, single_result=True)


            return result

        except Exception as e:
            self._handle_db_error(e, "select")
            return None

    def select(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """
        Execute SELECT query and return multiple rows
        Args:
            query (str): SQL query
            params (Dict, optional): Query parameters
        Returns:
            List[Dict]: List of records
        """
        try:
            typed_query = self._generate_typed_query(query, params) if params else query
            response = self.execute_statement(typed_query, params if params else {})

            # Get column names using existing method
            column_names = self._extract_column_names(query)

            return self._format_results(response=response, column_names=column_names)

        except Exception as e:
            self._handle_db_error(e, "select")
            return []


    def _handle_db_error(self, error: Exception, operation: str) -> None:
        """
        Handle database errors with specific error messages
        Args:
            error: The caught exception
            operation: The type of operation that failed (insert, update, delete, etc.)
        """
        error_str = str(error)

        # PostgreSQL error codes
        if "SQLState: 23505" in error_str:  # Unique violation
            constraint_name = error_str.split('"')[1] if '"' in error_str else "unknown"
            print(f"Duplicate key error in {operation}: The record already exists (constraint: {constraint_name})")

            # Handle specific constraints
            if "accounts_account_id_key" in error_str:
                print(f"Account already exists in the database")

        elif "SQLState: 23503" in error_str:  # Foreign key violation
            print(f"Foreign key violation in {operation}: Referenced record does not exist")

        elif "SQLState: 23502" in error_str:  # Not null violation
            print(f"Not null violation in {operation}: Required field is missing")

        else:
            print(f"{operation.capitalize()} error: {error_str}")

    def _get_postgres_type(self, col: str, typecast_map: Dict) -> Optional[str]:
        """Get the PostgreSQL type for a column"""
        for pg_type, columns in TYPE_CASTING.items():
            if col in columns:
                return pg_type
        return None

    def execute_statement(self, sql: str, parameters: Optional[Dict] = None) -> Dict:
        """
        Execute a single SQL statement
        """
        try:
            params = {
                'resourceArn'   : self.cluster_arn,
                'secretArn'     : self.secret_arn,
                'database'      : self.database,
                'sql'           : sql
            }

            if parameters:
                params['parameters'] = self._format_parameters(parameters)

            response = self.client.execute_statement(**params)
            return response

        except Exception as e:
            self._handle_db_error(e, "execute")
            raise

    def begin_transaction(self) -> str:
        """
        Start a new transaction and return the transaction ID
        """
        try:
            response = self.client.begin_transaction(
                resourceArn = self.cluster_arn,
                secretArn   = self.secret_arn,
                database    = self.database
            )
            return response['transactionId']
        except ClientError as e:
            print(f"Failed to begin transaction: {e}")
            raise

    def execute_transaction(self, sql_statements: List[Dict], transaction_id: str) -> List[Dict]:
        """
        Execute multiple SQL statements in a transaction
        """
        try:
            results = []
            for statement in sql_statements:
                params = {
                    'resourceArn'   : self.cluster_arn,
                    'secretArn'     : self.secret_arn,
                    'database'      : self.database,
                    'sql'           : statement['sql'],
                    'transactionId' : transaction_id
                }

                if 'parameters' in statement:
                    params['parameters'] = self._format_parameters(statement['parameters'])

                response = self.client.execute_statement(**params)
                results.append(response)

            return results

        except ClientError as e:
            print(f"Transaction execution failed: {e}")
            self.rollback_transaction(transaction_id)
            raise

    def commit_transaction(self, transaction_id: str) -> None:
        """
        Commit a transaction
        """
        try:
            self.client.commit_transaction(
                resourceArn     = self.cluster_arn,
                secretArn       = self.secret_arn,
                transactionId   = transaction_id
            )
        except ClientError as e:
            print(f"Failed to commit transaction: {e}")
            raise

    def rollback_transaction(self, transaction_id: str) -> None:
        """
        Rollback a transaction
        """
        try:
            self.client.rollback_transaction(
                resourceArn     = self.cluster_arn,
                secretArn       = self.secret_arn,
                transactionId   = transaction_id
            )
        except ClientError as e:
            print(f"Failed to rollback transaction: {e}")
            raise

    def batch_execute_statement(self, sql: str, parameter_sets: List[Dict]) -> Dict:
        """
        Execute a batch SQL statement
        """
        try:
            formatted_parameter_sets = [self._format_parameters(params) for params in parameter_sets]

            response = self.client.batch_execute_statement(
                resourceArn     = self.cluster_arn,
                secretArn       = self.secret_arn,
                database        = self.database,
                sql             = sql,
                parameterSets   = formatted_parameter_sets
            )
            return response

        except ClientError as e:
            print(f"Batch execution failed: {e}")
            raise

    def process_results(self, response: Dict) -> List[Dict]:
        """
        Process and format query results
        """
        if 'records' not in response:
            return []
        formatted_results = []
        for record in response['records']:
            row = {}
            for i, value in enumerate(record):
                # Get the first key-value pair from the value dictionary
                field_type, field_value = next(iter(value.items()))
                row[f"column_{i}"] = field_value
            formatted_results.append(row)

        return formatted_results

    def select(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """
        Execute SELECT query and return multiple rows
        Args:
            query (str): SQL query
            params (Dict, optional): Query parameters
        Returns:
            List[Dict]: List of records
        """
        try:
            typed_query = self._generate_typed_query(query, params) if params else query
            response = self.execute_statement(typed_query, params if params else {})

            if not response or 'records' not in response or not response['records']:
                return []

            # Get column names using existing method
            column_names    = self._extract_column_names(query)
            results         = self._format_results(response=response, column_names=column_names)



            return results

        except Exception as e:
            self._handle_db_error(e, "select")
            return []

    def select_one(self, query: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Execute SELECT query and return single row
        Args:
            query (str): SQL query
            params (Dict, optional): Query parameters
        Returns:
            Optional[Dict]: Single record or None
        """
        try:
            typed_query = self._generate_typed_query(query, params) if params else query
            response    = self.execute_statement(typed_query, params if params else {})

            if not response or 'records' not in response or not response['records']:
                return None

            # Get column names using existing method
            results         = []
            column_names    = self._extract_column_names(query)

            results         = self._format_results(response=response, column_names=column_names)
            result          = results[0]


            return result

        except Exception as e:

            self._handle_db_error(e, "select")
            return None

    def _generate_typed_query(self, query: str, params: Dict) -> str:
        """Helper method to generate typed query"""
        typed_query = query
        for param in params.keys():
            typed_placeholder = (
                f":{param}::{self._get_postgres_type(param, AWS_TYPECAST_2)}"
                if self._get_postgres_type(param, AWS_TYPECAST_2)
                else f":{param}"
            )
            typed_query = typed_query.replace(f":{param}", typed_placeholder)
        return typed_query

    def insert(self, table: str, data: Dict[str, Any]) -> Optional[int]:
        """
        Insert single record
        Args:
            table (str): Table name
            data (Dict): Data to insert
        Returns:
            Optional[int]: ID of inserted record or None if error
        """
        try:
            columns         = list(data.keys())
            placeholders    = [
                                f":{col}::{self._get_postgres_type(col, AWS_TYPECAST_2)}"
                                if self._get_postgres_type(col, AWS_TYPECAST_2)
                                else f":{col}"
                                for col in columns
                              ]

            display = columns.copy()
            display.insert(0,'id')

            query = f"""
                INSERT INTO {table} ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
                RETURNING {', '.join(display)}
            """

            response = self.execute_statement(query, data)
            columns.insert(0, 'id')
            results         = self._format_results(response=response, column_names=columns)

            return results[0] if response else None

        except Exception as e:
            self._handle_db_error(e, "insert")
            print(str(e))
            return None

    def bulk_insert(self, table: str, data: List[Dict[str, Any]]) -> bool:
        """
        Insert multiple records
        Args:
            table (str): Table name
            data (List[Dict]): List of records to insert
        Returns:
            bool: Success status
        """
        if not data:
            return False

        try:
            columns = list(data[0].keys())

            placeholders    = [
                                f":{col}::{self._get_postgres_type(col, AWS_TYPECAST_2)}"
                                if self._get_postgres_type(col, AWS_TYPECAST_2)
                                else f":{col}"
                                for col in columns
                              ]

            query = f"""
                INSERT INTO {table} ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
            """

            response = self.batch_execute_statement(query, data)
            return True
        except Exception as e:
            self._handle_db_error(e, "insert")
            print(f"Bulk insert error: {str(e)}")
            return False

    def update(self, table: str, data: Dict[str, Any], condition: str, params: Dict) -> bool:
        """
        Update records
        Args:
            table (str): Table name
            data (Dict): Data to update
            condition (str): WHERE clause
            params (Dict): Condition parameters
        Returns:
            bool: Success status
        """
        try:
            set_clause = ", ".join([
                f"{k} = :{k}::{self._get_postgres_type(k, AWS_TYPECAST_2)}"
                if self._get_postgres_type(k, AWS_TYPECAST_2)
                else f"{k} = :{k}"
                for k in data.keys()
            ])

            query = f"""
                UPDATE {table}
                SET {set_clause}
                WHERE {condition}
            """

            # Merge data and params dictionaries
            all_params = {**data, **params}

            self.execute_statement(query, all_params)
            return True

        except Exception as e:
            print(f"Update error: {str(e)}")
            return False

    def delete(self, table: str, condition: str, params: Dict) -> bool:
        """
        Delete records
        Args:
            table (str): Table name
            condition (str): WHERE clause
            params (Dict): Condition parameters
        Returns:
            bool: Success status
        """
        try:
            # Generate placeholders with type casting for each parameter
            typed_params = [
                f":{param}::{self._get_postgres_type(param, AWS_TYPECAST_2)}" if self._get_postgres_type(param, AWS_TYPECAST_2)
                else f":{param}"
                for param in params.keys()
            ]

            # Replace original placeholders with typed ones in the condition
            typed_condition = condition
            for param, typed_param in zip(params.keys(), typed_params):
                typed_condition = typed_condition.replace(f":{param}", typed_param)

            query = f"DELETE FROM {table} WHERE {typed_condition}"

            self.execute_statement(query, params)
            return True
        except Exception as e:
            print(f"Delete error: {str(e)}")
            print(f"Query: {query}")
            print(f"Parameters: {params}")
            return False

    def execute(self, sql: str, parameters: Dict[str, Any]) -> Dict:
        """
        Execute a SQL statement with parameters
        """
        try:
            formatted_parameters = []
            for k, v in parameters.items():
                param = {
                    'name': k,
                    'value': {'stringValue': str(v)} if v is not None else {'isNull': True}
                }
                formatted_parameters.append(param)

            response = self.client.execute_statement(
                resourceArn=self.cluster_arn,
                secretArn=self.secret_arn,
                database=self.database,
                sql=sql,
                parameters=formatted_parameters
            )
            return response
        except Exception as e:
            print(f"Database operation failed: {str(e)}")
            raise

    def execute_transaction(self, queries: List[Dict[str, Any]]) -> bool:
        """
        Execute multiple queries in a transaction
        Args:
            queries (List[Dict]): List of dictionaries containing 'sql' and optional 'parameters'
        Returns:
            bool: Success status
        """
        try:
            transaction_id = self.begin_transaction()
            try:
                results = super().execute_transaction(queries, transaction_id)
                self.commit_transaction(transaction_id)
                return True
            except Exception as e:
                self.rollback_transaction(transaction_id)
                raise e
        except Exception as e:
            print(f"Transaction error: {str(e)}")
            return False

""" 4. CORE DB MANAGER """
class CoreUpdateDb:
    def __init__(self):

        self.sts_client = boto3.client('sts')
        self.db         = DBManager(database_name=DB_NAME, cluster_arn=ARN_AURORA, secret_arn=ARN_SECRET)
        self.sqs        = SQSManager(queue_arn=ARN_SQS)
        self.handle_arr = []

        self.stats      = {
                            'CREATED': 0,
                            'UPDATED': 0,
                            'SKIPPED': 0
                          }

        self.data       = []

    def fetch_data(self, max_messages=10):
        data = []
        try:
            received_messages = self.sqs.receive_messages(max_messages=max_messages, wait_time_seconds=0)
            for message in received_messages:
                data.append(json.loads(message.get('Body')))

                sqs_details =   {
                                    "receipt_handle"    :  message['ReceiptHandle'],
                                    "message_id"        : message['MessageId']
                                }
                self.handle_arr.append(sqs_details)

            #with open('aws_data.json', 'w') as f:
            #    json.dump(message, f, indent=4)
            #self.sqs.purge_queue()
            return data
        except Exception as e:
            print(f"fetch_data error: {str(e)}")

    def _convert_python_list_string_to_array(self, input_data: Union[str, List]) -> str:
        """
        Convert either a Python list string representation or actual list to a PostgreSQL array
        """
        try:
            elements = []

            if isinstance(input_data, str):
                # Handle string representation of list
                cleaned_string = input_data.strip('[]')
                if not cleaned_string:
                    return "{}"
                # Split by comma and clean up each element
                elements = [elem.strip().strip("'").strip('"') for elem in cleaned_string.split(',')]

            elif isinstance(input_data, list):
                # Handle actual list
                elements = [str(elem).strip().strip("'").strip('"') for elem in input_data]

            else:
                print(f"Unsupported input type: {type(input_data)}")
                return "{}"

            # Convert to PostgreSQL array format
            postgres_array = "{" + ",".join(f'"{elem}"' for elem in elements if elem) + "}"

            return postgres_array

        except Exception as e:
            print(f"Error converting to array: {str(e)}")
            return "{}"

    #1. Process and insert/update Account Data
    def process_account(self, data: Dict[str, Any]) -> Dict[str, Any]:
        response = {
            'success': False,
            'id': None,
            'stats': {
                'created': 0,
                'updated': 0,
                'skipped': 0
            }
        }

        try:
            # Check if account exists using select_one
            check_query = """
                SELECT id, account_id
                FROM accounts
                WHERE account_id = :account_id
            """

            existing_account = self.db.select_one(check_query, {"account_id": data['account_id']})

            # Prepare parameters
            account_data = {
                'account_id'        : data['account_id'],
                'account_name'      : data['account_name'] if(data['account_name'] != None) else data['account_id'],
                'account_email'     : data['account_email'] if(data['account_email'] != None) else 'Access Restricted',
                'account_status'    : data['account_status'],
                'account_arn'       : data['account_arn'] if(data['account_arn'] != None) else 'Access Restricted',
                'joined_method'     : data['joined_method'] if(data['joined_method'] != None) else 'Access Restricted',
                'joined_timestamp'  : data['joined_timestamp'] if(data['joined_timestamp'] != None) else date.today()
            }

            print(account_data)
            try:
                if not existing_account:
                    # Insert new account
                    result = self.db.insert('accounts', account_data)
                    if result:
                        response['id']                  = result['id']
                        response['stats']['created']    += 1
                        response['success']             = True
                        print(f"Created new account for {result['account_id']}")
                    else:
                        raise Exception("Failed to insert new account")
                else:
                    # Update existing account
                    account_data['updated_at']  = datetime.now()
                    condition                   = "account_id = :account_id"
                    result                      = self.db.update('accounts', account_data, condition, {"account_id": data['account_id']})

                    if result:
                        response['id']          = existing_account['id']
                        response['stats']['updated']    += 1
                        response['success']             = True
                    else:
                        response['stats']['skipped']    += 1
                        response['success']             = False

                if not response['id']:
                    raise Exception("Failed to create or update account")

                self.stats['CREATED'] += response['stats']['created']
                self.stats['UPDATED'] += response['stats']['updated']
                self.stats['SKIPPED'] += response['stats']['skipped']

                return response

            except Exception as e:
                print(f"Account Processing Error: {str(e)}")
                return response

        except Exception as e:
            print(f"Account Checking Error: {str(e)}")
            return response

    #2. Process Service Data

    def process_services(self, account_pk: int, data: List[Dict[str, Any]]) -> bool:
        """
        Process and insert services data for an account, handling duplicates
        """
        inserted_count = 0
        skipped_count = 0
        updated_count = 0

        try:
            for service_data in data:
                try:
                    # Check for duplicate using select_one
                    check_query = """
                        SELECT id
                        FROM services
                        WHERE account_id = :account_id
                        AND service = :service
                        AND date_from = :date_from
                        AND date_to = :date_to
                    """
                    check_params = {
                        'account_id'    : account_pk,
                        'service'       : service_data['service'],
                        'date_from'     : service_data['date_from'],
                        'date_to'       : service_data['date_to']
                    }

                    existing_service    = self.db.select_one(check_query, check_params)
                    # Convert usage_types to proper PostgreSQL array format
                    usage_types         = service_data.get('usage_types', [])
                    usage_types_str     = self._convert_python_list_string_to_array(usage_types)

                    # Prepare the service parameters

                    service_params = {
                        'account_id'        : account_pk,
                        'service'           : service_data['service'],
                        'date_from'         : service_data['date_from'],
                        'date_to'           : service_data['date_to'],
                        'cost'              : service_data['cost'],
                        'currency'          : service_data.get('currency', 'USD'),
                        'utilization'       : service_data.get('utilization') if service_data.get('utilization') is not None else None,
                        'utilization_unit'  : service_data.get('utilization_unit'),
                        'usage_types'       : usage_types_str
                    }

                    if existing_service:

                        # Check existing data
                        check_existing_query = """
                            SELECT cost, currency, utilization, utilization_unit, usage_types
                            FROM services
                            WHERE id = :service_id
                        """
                        existing_data = self.db.select_one(check_existing_query,{'service_id': existing_service['id']})
                        if existing_data:

                            # Check if data has changed
                            if self._is_service_data_changed(existing_data, service_params):

                                # Update only if data has changed
                                service_params['service_id'] = str(existing_service['id'])

                                update_columns = {
                                    'cost'              : service_params['cost'],
                                    'currency'          : service_params['currency'],
                                    'utilization'       : service_params['utilization'],
                                    'utilization_unit'  : service_params['utilization_unit'],
                                    'usage_types'       : service_params['usage_types'],
                                    'updated_at'        : datetime.now()
                                }
                                service_params['service_id'] = int(service_params['service_id'])

                                if self.db.update('services', update_columns, 'id = :service_id', service_params):
                                    updated_count += 1
                                else:
                                    raise Exception(f"Failed to update service: {service_data['service']}")
                            else:
                                skipped_count += 1
                    else:

                        # Insert new service

                        insert_columns = {
                            'account_id': service_params['account_id'],
                            'service': service_params['service'],
                            'date_from': service_params['date_from'],
                            'date_to': service_params['date_to'],
                            'cost': service_params['cost'],
                            'currency': service_params['currency'],
                            'utilization': service_params['utilization'],
                            'utilization_unit': service_params['utilization_unit'],
                            'usage_types': service_params['usage_types']
                        }

                        if self.db.insert('services', insert_columns):
                            inserted_count += 1
                        else:
                            raise Exception(f"Failed to insert service: {service_data['service']}")

                except Exception as e:
                    print(f"Error processing service {service_data.get('service')}: {str(e)}")
                    raise

            #print(f"Processing complete: {inserted_count} inserted, {updated_count} updated, {skipped_count} skipped")
            self.stats['CREATED']   += inserted_count
            self.stats['UPDATED']    += updated_count
            self.stats['SKIPPED']   += skipped_count

            return  True

        except Exception as e:
            print(f"Error processing services data: {str(e)}")
            return False

    def _is_service_data_changed(self, existing_data: Dict, new_params: Dict) -> bool:
        """Helper method to check if service data has changed"""
        return (
            existing_data['cost'] != new_params['cost'] or
            existing_data['currency'] != new_params['currency'] or
            existing_data['utilization'] != new_params['utilization'] or
            existing_data['utilization_unit'] != new_params['utilization_unit'] or
            existing_data['usage_types'] != new_params['usage_types'].replace('{','').replace('}','')
        )


    #3a. Checking if there is an existing cost data available fo rthe account_id
    def check_existing_cost_report(self, account_id: int, period_start: str, period_end: str) -> Dict:
        """Check if a cost report already exists"""
        query = """
            SELECT id, current_period_cost, previous_period_cost,
                cost_difference, cost_difference_percentage,
                potential_monthly_savings, anomalies_detected,
                saving_opportunities_count
            FROM cost_reports
            WHERE account_id = :account_id
            AND period_start = :period_start
            AND period_end = :period_end
        """
        params = {
            'account_id': account_id,
            'period_start': period_start,
            'period_end': period_end
        }
        return self.db.select_one(query, params)

    def has_data_changed(self, existing: Dict, new: Dict) -> bool:
        """Compare existing and new data"""
        fields_to_compare = [
            'current_period_cost', 'previous_period_cost',
            'cost_difference', 'cost_difference_percentage',
            'potential_monthly_savings', 'anomalies_detected',
            'saving_opportunities_count'
        ]

        return any(
            abs(float(existing.get(field, 0)) - float(new.get(field, 0))) > 0.0001
            for field in fields_to_compare
        )

    def process_cost_data(self, account_id: int, data: List[Dict]) -> Dict:
        """Process cost data with duplicate handling"""
        try:
            # Process each cost report in the data

            for report in data:

                # Check for existing cost report
                existing_report = self.check_existing_cost_report(
                    account_id,
                    report['period']['start'],
                    report['period']['end']
                )
                #print(report)
                # Prepare cost report data
                cost_report_data = {
                    'account_id': account_id,
                    'current_period_cost': report.get('current_period_cost', 0),
                    'previous_period_cost': report.get('previous_period_cost', 0),
                    'cost_difference': report.get('cost_difference', 0),
                    'cost_difference_percentage': report.get('cost_difference_percentage', 0),
                    'potential_monthly_savings': report.get('potential_monthly_savings', 0),
                    'anomalies_detected': report.get('anomalies_detected', 0),
                    'saving_opportunities_count': report.get('saving_opportunities_count', 0),
                    'period_start': report['period']['start'],
                    'period_end': report['period']['end'],
                    'period_granularity': report['period']['granularity']
                }


                cost_report_id = None
                if existing_report:
                    if self.has_data_changed(existing_report, cost_report_data):
                        # Update existing report
                        update_success = self.db.update(table='cost_reports',
                                                        data=cost_report_data,
                                                        condition='id = :id',
                                                        params=existing_report)

                        if update_success:
                            cost_report_id = existing_report['id']
                            self.stats['UPDATED'] += 1
                        else:
                            raise Exception("Failed to update cost report")
                    else:
                        self.stats['SKIPPED'] += 1
                        continue
                else:
                    # Insert new cost report
                    cost_report = self.db.insert('cost_reports', cost_report_data)
                    cost_report_id = cost_report['id']

                    print(cost_report_id)

                    if cost_report_id:
                        self.stats['CREATED'] += 1
                    else:
                        raise Exception("Failed to insert cost report")

                # Clean up existing related records
                self.db.delete('service_costs', 'cost_report_id = :cost_report_id', {'cost_report_id': cost_report_id})
                self.db.delete('cost_forecasts', 'cost_report_id = :cost_report_id', {'cost_report_id': cost_report_id})

                # Process service costs
                if report.get('top_services'):
                    service_costs = [
                        {
                            'cost_report_id': cost_report_id,
                            'service_name': service.get('service', ''),
                            'cost': service.get('cost', 0)
                        }
                        for service in report['top_services']
                    ]

                    if service_costs and not self.db.bulk_insert('service_costs', service_costs):
                        raise Exception("Failed to insert service costs")

                # Process forecasts
                if report.get('forecast'):
                    forecasts = [
                        {
                            'cost_report_id': cost_report_id,
                            'period_start': forecast['period']['start'],
                            'period_end': forecast['period']['end'],
                            'amount': forecast.get('amount', 0),
                            'prediction_interval_lower_bound': forecast.get('prediction_interval_lower_bound', 0),
                            'prediction_interval_upper_bound': forecast.get('prediction_interval_upper_bound', 0)
                        }
                        for forecast in report['forecast']
                    ]

                    if forecasts and not self.db.bulk_insert('cost_forecasts', forecasts):
                        raise Exception("Failed to insert forecasts")

            return self.stats

        except Exception as e:
            print(f"Error processing cost data: {str(e)}")
            raise

    #4. Security
    def _finding_exists(self, finding):
        """Check if finding already exists"""
        query = """
            SELECT id FROM findings
            WHERE  finding_id = :finding_id
            AND resource_id = :resource_id
            AND security_id = :security_id
        """
        params = {
            'finding_id': finding.get('finding_id'),
            'resource_id': finding.get('resource_id'),
            'security_id': finding.get('security_id')
        }
        return self.db.select_one(query, params)

    def process_security_data(self, account_id: int, security_data: Dict) -> None:
        """
        Process single security service data
        """
        try:
            # Check if security record exists
            sql     = "SELECT id FROM security WHERE account_id = :account_id AND service = :service"
            params  = {  'account_id': account_id,
                        'service': security_data['service']
                    }

            existing_security = self.db.select_one(sql, params)

            # Prepare security record with counts from severity_counts
            security_record = {
                'account_id'                : account_id,
                'service'                   : security_data['service'],
                'total_findings'            : security_data['total_findings'],
                'critical_count'            : security_data['severity_counts'].get('CRITICAL', 0),
                'high_count'                : security_data['severity_counts'].get('HIGH', 0),
                'medium_count'              : security_data['severity_counts'].get('MEDIUM', 0),
                'low_count'                 : security_data['severity_counts'].get('LOW', 0),
                'informational_count'       : security_data['severity_counts'].get('INFORMATIONAL', 0),
                'open_findings'             : security_data['open_findings'],
                'resolved_findings'         : security_data['resolved_findings']
            }

            # Update or insert security record
            if existing_security:
                up = self.db.update(table="security", data=security_record, condition="id = :id", params={"id": existing_security['id']})
                security_id = existing_security['id'] if up else None

            else:
                hasCreated  = self.db.insert(table="security", data=security_record)
                security_id = hasCreated

            if not security_id:
                raise Exception(f"Failed to handle security record for service {security_data['service']}")

            # Process findings
            if(len(security_data['findings']) > 0):
                # Process findings
                successful_inserts = 0
                successful_updates = 0

                for finding in security_data['findings']:
                    try:
                        # Add security_id to the finding
                        finding['security_id'] = security_id

                        # Check if finding exists
                        existing_finding = self._finding_exists(finding)

                        if existing_finding is not None:
                            # Update existing finding
                            condition = "id = :id"
                            finding['updated_at'] = datetime.now()

                            if self.db.update("findings", finding, condition, {'id': existing_finding['id']}):
                                successful_updates += 1
                            else:
                                print(f"Failed to update finding: {existing_finding['id']}")
                        else:
                            # Insert new finding
                            if self.db.insert("findings", finding):
                                successful_inserts += 1
                            else:
                                print(f"Failed to insert finding: {finding.get('id')}")

                    except Exception as e:
                        print(f"Error processing finding {finding['finding_id']}: {str(e)}")
                        continue

                #print(f"Processing completed: {successful_inserts} inserted, {successful_updates} updated")
                self.stats['CREATED']   += successful_inserts
                self.stats['UPDATED']    += successful_updates

                return  True

        except Exception as e:
            print(f"Error processing security data: {str(e)}")
            raise

    def load_security_findings(self, data: List[Dict], account_id: int) -> Dict:
        """
        Main function to load security findings from API data
        """
        try:
            # Process each security service data
            for security_data in data:
                self.process_security_data(account_id, security_data)

            #print(f"Loading complete: {self.stats}")
            return self.stats

        except Exception as e:
            print(f"Error: {str(e)}")
            self.stats['CREATED']   += 0
            self.stats['UPDATED']    += 0
            self.stats['SKIPPED']   += 0

            return True

    #5. Process Logs
    def process_logs(self, data):
        try:
            print(data)
        except Exception as e:
            print(f"process_account error: {str(e)}")

    def load_from_sqs(self, max_messages=10):
        data            = []

        #1. Fetch Data From Queue
        data            = self.fetch_data(max_messages=max_messages)
        account_id   = None
        count       = 0
        print(f"TOTAL DATASETS FOUND in QUEUE: {len(data)}")
        if(len(data) > 0):
            for d in data:

                #2. Load Account Data
                account         = self.process_account(data=d['account'])
                account_id      = account['id']


                if(account_id):
                    #3. Load Services Data
                    self.process_services(account_pk=account_id, data=d['service'])
                    #4. Load Cost Data
                    self.process_cost_data(account_id= account_id, data=d['cost'])
                    #print("-"*100)
                    #5. Load Security Data
                    self.load_security_findings(account_id= account_id, data=d['security'])
                    #print("-"*100)
                    #6. Load Logs Data
                    #core.process_security(data=d['logs'])
                    #print("*"*100)
                    rh = self.handle_arr[count]
                    self.sqs.delete_message(receipt_handle=rh['receipt_handle'])
                    print(f'deleted: {rh}')
                    count = count + 1

            print(f"{SUCCESS} Loaded {count} set(s) of data to {DB_NAME} ")
            return self.stats
            #print(len(data))
        else:
            print(f"{ERROR} EMPTY SQS: {ARN_SQS}")

    def load_from_file(self, json_file_path):
        try:
            # Read the JSON file
            print(f"Reading data from {json_file_path}")
            with open(json_file_path, 'r') as file:
                file_data = json.load(file)

            if not file_data.get('data'):
                print("No data found in file")
                return

            count = 0
            total_records = len(file_data['data'])
            account_id = None

            print(f"Found {total_records} records to process")

            for d in file_data['data']:
                try:
                    print(f"\nProcessing record {count + 1}/{total_records}")
                    print("-" * 50)

                    # 1. Load Account Data
                    #account = core.process_account(data=d.get('account', {}))
                    #account_id = account.get('id')

                    if not account_id:
                        print("✗ No account ID found, skipping record")
                        #continue

                    #print(f"✓ Account processed: {account_id}")

                    # 2. Load Services Data
                    if 'service' in d:
                        #core.process_services(account_pk=account_id, data=d['service'])
                        print("✓ Services data processed")
                    else:
                        print("- No services data found")

                    # 3. Load Cost Data
                    if 'cost' in d:
                        #core.process_cost_data(account_id=account_id, data=d['cost'])
                        print("✓ Cost data processed")
                    else:
                        print("- No cost data found")

                    # 4. Load Security Data
                    if 'security' in d:
                        #core.load_security_findings(account_id=account_id, data=d['security'])
                        print("✓ Security data processed")
                    else:
                        print("- No security data found")

                    # Optional: Load Logs Data
                    if 'logs' in d:
                    #     core.process_security(data=d['logs'])
                        print("✓ Logs data processed")

                    count += 1
                    print(f"Progress: {count}/{total_records} records processed")

                except Exception as e:
                    print(f"✗ Error processing record: {str(e)}")
                    continue

            print("\nProcessing Summary")
            print(f"Total records           : {total_records}")
            print(f"Successfully processed  : {count}")
            print(f"Failed                  : {total_records - count}")

        except FileNotFoundError:
            print(f"✗ Error: The file {json_file_path} was not found")
        except json.JSONDecodeError:
            print(f"✗ Error: The file {json_file_path} contains invalid JSON")
        except Exception as e:
            print(f"✗ Error: An unexpected error occurred: {str(e)}")

""" 5. METHODS FOR LAMBDA """
def test_connection():
    check = TestAwsServices()
    return check.test_obs_360_connection()

def lambda_handler(event=None, context=None):
    if(test_connection()):
        try:
            # Get max_messages from event or use default value of 10
            max_messages = 10
            if event and isinstance(event, dict) and 'max_messages' in event:
                max_messages = int(event['max_messages'])

            core = CoreUpdateDb()  # Replace with your core class initialization
            test = core.load_from_sqs(max_messages=max_messages)
            #print(test)
        except Exception as e:
            print(f"Failed to process file: {str(e)}")
    else:
        return False

# Uncomment the line below for development only
#if __name__ == "__main__":
#    lambda_handler()