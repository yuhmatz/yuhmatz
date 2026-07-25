-- SIMULATED BACKUP FILE — White Hat Lab training environment.
-- Everything below is FAKE sample data created for education. No real system,
-- person, or credential is represented here.
--
-- FINDING: a database dump reachable over HTTP without authentication.
-- Real-world impact: instant disclosure of password hashes and customer PII.

CREATE TABLE users (id INTEGER, username TEXT, password TEXT, role TEXT, email TEXT);

INSERT INTO users VALUES (1,'admin','S3cr3t-Admin-Pw!','administrator','admin@whitehatlab.local');
INSERT INTO users VALUES (2,'alice','password123','user','alice@whitehatlab.local');
INSERT INTO users VALUES (3,'bob','hunter2','user','bob@whitehatlab.local');
INSERT INTO users VALUES (4,'auditor','letmein','auditor','auditor@whitehatlab.local');

-- REMEDIATION: store backups outside the web root, encrypt them at rest,
-- restrict access by IAM policy, and never serve them from the app server.
