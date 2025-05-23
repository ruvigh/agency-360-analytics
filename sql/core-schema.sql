USE core;
/* Account Table Schema */
-- Create the main accounts table
CREATE TABLE accounts (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(12) NOT NULL UNIQUE,
    account_name VARCHAR(255) NOT NULL,
    account_email VARCHAR(255) NOT NULL,
    account_status VARCHAR(50) NOT NULL,
    account_arn VARCHAR(255) NOT NULL,
    joined_method VARCHAR(50) NOT NULL,
    joined_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    account_type VARCHAR(50),
    csp VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create the contact_info table
CREATE TABLE contact_info (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(12) REFERENCES accounts(account_id),
    address_line1 VARCHAR(255),
    address_line2 VARCHAR(255),
    address_line3 VARCHAR(255),
    city VARCHAR(100),
    country_code VARCHAR(2),
    postal_code VARCHAR(20),
    state_or_region VARCHAR(100),
    company_name VARCHAR(255),
    phone_number VARCHAR(20),
    website_url VARCHAR(255),
    full_name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_id)
);

-- Create the alternate_contacts table
CREATE TABLE alternate_contacts (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(12) REFERENCES accounts(account_id),
    contact_type VARCHAR(50) NOT NULL,  -- 'billing', 'operations', 'security'
    full_name VARCHAR(255),
    title VARCHAR(255),
    email VARCHAR(255),
    phone_number VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_id, contact_type)
);



/* Services Table Schema */
-- Create the services table
CREATE TABLE services (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    service VARCHAR(255) NOT NULL,
    date_from DATE NOT NULL,
    date_to DATE NOT NULL,
    cost DECIMAL(20,10) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    utilization DECIMAL(20,10),
    utilization_unit VARCHAR(100),
    usage_types VARCHAR[] DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT date_check CHECK (date_to >= date_from)
);


/*Cost Table Schema*/
-- Create enum for period granularity
CREATE TYPE period_granularity_type AS ENUM ('MONTHLY', 'WEEKLY', 'DAILY');

-- Create the main cost reports table
CREATE TABLE cost_reports (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    current_period_cost NUMERIC(20,10) NOT NULL,
    previous_period_cost NUMERIC(20,10) NOT NULL,
    cost_difference NUMERIC(20,10) NOT NULL,
    cost_difference_percentage NUMERIC(20,10) NOT NULL,
    potential_monthly_savings NUMERIC(20,10) DEFAULT 0,
    anomalies_detected INTEGER DEFAULT 0,
    saving_opportunities_count INTEGER DEFAULT 0,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    period_granularity period_granularity_type NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create the services cost table for top services
CREATE TABLE service_costs (
    id SERIAL PRIMARY KEY,
    cost_report_id INTEGER REFERENCES cost_reports(id) ON DELETE CASCADE,
    service_name VARCHAR(255) NOT NULL,
    cost NUMERIC(20,10) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create the forecast table
CREATE TABLE cost_forecasts (
    id SERIAL PRIMARY KEY,
    cost_report_id INTEGER REFERENCES cost_reports(id) ON DELETE CASCADE,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    amount NUMERIC(20,10) NOT NULL,
    prediction_interval_lower_bound NUMERIC(20,10),
    prediction_interval_upper_bound NUMERIC(20,10),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


/* Security */

-- Create the security table

CREATE TABLE security (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    service VARCHAR(255) NOT NULL,
    total_findings INTEGER NOT NULL DEFAULT 0,
    critical_count INTEGER NOT NULL DEFAULT 0,
    high_count INTEGER NOT NULL DEFAULT 0,
    medium_count INTEGER NOT NULL DEFAULT 0,
    low_count INTEGER NOT NULL DEFAULT 0,
    informational_count INTEGER NOT NULL DEFAULT 0,
    open_findings INTEGER NOT NULL DEFAULT 0,
    resolved_findings INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create the findings table
CREATE TABLE findings (
    id SERIAL PRIMARY KEY,
    security_id INTEGER NOT NULL REFERENCES security(id) ON DELETE CASCADE,
    finding_id VARCHAR(255) NOT NULL,
    service VARCHAR(255) NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    severity VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    resource_type VARCHAR(255),
    resource_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    recommendation TEXT,
    compliance_status VARCHAR(50),
    region VARCHAR(50),
    workflow_state VARCHAR(50),
    record_state VARCHAR(50),
    product_name VARCHAR(255),
    company_name VARCHAR(255),
    product_arn VARCHAR(255),
    generator_id VARCHAR(255),
    generator VARCHAR(255),
    UNIQUE(finding_id)
);

/* Create Product Table */
-- Create the products table
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    owner VARCHAR(255) NOT NULL,
    position VARCHAR(255),
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create the product_accounts junction table
CREATE TABLE product_accounts (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(product_id, account_id)
);


-- Create the logs table
CREATE TABLE logs (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    date_created TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    account_status VARCHAR(50) NOT NULL,
    cost_status VARCHAR(50) NOT NULL,
    service_status VARCHAR(50) NOT NULL,
    security_status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create the log_messages table for storing messages
CREATE TABLE log_messages (
    id SERIAL PRIMARY KEY,
    log_id INTEGER NOT NULL REFERENCES logs(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    message_type VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

/* Set Indexes */

-- Create indexes for better query performance
CREATE INDEX idx_accounts_account_id ON accounts(account_id);
CREATE INDEX idx_accounts_account_status ON accounts(account_status);
CREATE INDEX idx_contact_info_account_id ON contact_info(account_id);
CREATE INDEX idx_alternate_contacts_account_id ON alternate_contacts(account_id);

-- Accounts - Create indexes for better query performance
CREATE INDEX idx_services_account_id ON services(account_id);
CREATE INDEX idx_services_service ON services(service);
CREATE INDEX idx_services_date_range ON services(date_from, date_to);


-- Cost - Create indexes for better performance
CREATE INDEX idx_cost_reports_account_id ON cost_reports(account_id);
CREATE INDEX idx_service_costs_cost_report_id ON service_costs(cost_report_id);
CREATE INDEX idx_cost_forecasts_cost_report_id ON cost_forecasts(cost_report_id);
CREATE INDEX idx_cost_reports_period ON cost_reports(period_start, period_end);

-- Security -  Create indexes
CREATE INDEX idx_security_account_id ON security(account_id);
CREATE INDEX idx_security_service ON security(service);
CREATE INDEX idx_findings_security_id ON findings(security_id);
CREATE INDEX idx_findings_severity ON findings(severity);
CREATE INDEX idx_findings_status ON findings(status);
CREATE INDEX idx_findings_region ON findings(region);
CREATE INDEX idx_findings_generator ON findings(generator);

-- Products - Create indexes
CREATE INDEX idx_product_accounts_product_id ON product_accounts(product_id);
CREATE INDEX idx_product_accounts_account_id ON product_accounts(account_id);
CREATE INDEX idx_products_name ON products(name);
CREATE INDEX idx_products_owner ON products(owner);

-- Create index for frequent queries
CREATE INDEX idx_logs_account_id ON logs(account_id);
CREATE INDEX idx_logs_date_created ON logs(date_created);
CREATE INDEX idx_log_messages_log_id ON log_messages(log_id);
