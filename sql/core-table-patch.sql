--01 Table Modification

-- Remove UNIQUE constraint from account_email
ALTER TABLE accounts 
DROP CONSTRAINT IF EXISTS accounts_account_email_key;

-- Remove UNIQUE constraint from account_arn
ALTER TABLE accounts 
DROP CONSTRAINT IF EXISTS accounts_account_arn_key;

