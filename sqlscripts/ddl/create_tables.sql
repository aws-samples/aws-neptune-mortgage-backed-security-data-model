CREATE TABLE IF NOT EXISTS  mbs.borrower (
	borrower_id int4 NOT NULL,
	first_name varchar NULL,
	middle_name varchar NULL,
	last_name varchar NULL,
	age int4 NULL,
	address_type bpchar(5) NULL,
	address_1 varchar NULL,
	adderss_2 varchar NULL,
	city varchar NULL,
	state bpchar(2) NULL,
	zipcode varchar NULL,
	country varchar NULL,
	status bpchar(1) NULL,
	CONSTRAINT borrower_pkey PRIMARY KEY (borrower_id)
);


CREATE TABLE IF NOT EXISTS  mbs.loan (
	original_interest_rate float4 NULL,
	original_principal_balance float8 NULL,
	unpaid_principal_balance float8 NULL,
	loan_term int4 NULL,
	maturity_date varchar NULL,
	loan_id int8 NOT NULL,
	loan_status bpchar(1) NULL,
	issuance_date date NULL,
	CONSTRAINT loan_pkey PRIMARY KEY (loan_id)
);

CREATE TABLE IF NOT EXISTS  mbs."security" (
	security_value numeric NULL,
	issued_by varchar NULL,
	issued_date varchar NULL,
	cusip varchar NOT NULL,
	CONSTRAINT security_pkey PRIMARY KEY (cusip)
);


CREATE TABLE IF NOT EXISTS  mbs.seller (
	seller_id int4 NOT NULL,
	"name" varchar NULL,
	status bpchar(1) NULL,
	CONSTRAINT seller_pkey PRIMARY KEY (seller_id)
);


CREATE TABLE IF NOT EXISTS  mbs.servicer (
	servicer_id int4 NOT NULL,
	"name" varchar NULL,
	status bpchar(1) NULL,
	CONSTRAINT servicer_pkey PRIMARY KEY (servicer_id)
);

CREATE TABLE IF NOT EXISTS  mbs.property (
	property_id int4 NOT NULL,
	address_type bpchar(5) NULL,
	address_1 varchar NULL,
	adderss_2 varchar NULL,
	city varchar NULL,
	state bpchar(2) NULL,
	zipcode varchar NULL,
	country varchar NULL,
	CONSTRAINT property_pkey PRIMARY KEY (property_id)
);

CREATE TABLE IF NOT EXISTS  mbs.loan_activity (
	loan_id int8 NOT NULL,
	principal_pymnt float8 NOT NULL,
	int_pymnt float8 NOT NULL,
	rem_mnths_to_maturity int4 NULL,
	rem_unpaid_principal_balance float8 NULL,
	payment_date date NULL,
	activity_id int4 NOT NULL,
	CONSTRAINT loan_activity_pk PRIMARY KEY (activity_id)
);

CREATE TABLE IF NOT EXISTS  mbs.loan_property (
	loan_id int8 NOT NULL,
	property_id int4 NOT NULL
);

CREATE TABLE IF NOT EXISTS  mbs.loan_security (
	loan_id int8 NOT NULL,
	cusip varchar NOT NULL,
	percentage int8 NOT NULL
);

CREATE TABLE IF NOT EXISTS  mbs.loan_seller (
	loan_id int8 NOT NULL,
	seller_id int4 NOT NULL
);

CREATE TABLE IF NOT EXISTS  mbs.loan_servicer (
	loan_id int8 NOT NULL,
	servicer_id int4 NOT NULL
);

CREATE TABLE IF NOT EXISTS  mbs.loan_borrower (
	loan_id int8 NOT NULL,
	borrower_id int4 NOT NULL
);