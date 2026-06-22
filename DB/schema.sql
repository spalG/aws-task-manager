-- ─────────────────────────────────────────────────────────────
-- TaskFlow — MySQL Schema
-- Run once on your RDS instance after provisioning
-- mysql -h <RDS_ENDPOINT> -u admin -p taskflow < schema.sql
-- ─────────────────────────────────────────────────────────────

CREATE DATABASE IF NOT EXISTS taskflow
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE taskflow;

-- ── Tasks table ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tasks (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    title       VARCHAR(255)                         NOT NULL,
    description TEXT,
    priority    ENUM('low','medium','high')           NOT NULL DEFAULT 'medium',
    status      ENUM('todo','in_progress','done')     NOT NULL DEFAULT 'todo',
    assigned_to VARCHAR(100),
    due_date    DATE,
    created_at  DATETIME                             NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME                             NOT NULL DEFAULT CURRENT_TIMESTAMP
                                                              ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_status   (status),
    INDEX idx_priority (priority),
    INDEX idx_due_date (due_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Seed data (optional — remove in prod) ────────────────────
INSERT INTO tasks (title, description, priority, status, assigned_to, due_date) VALUES
  ('Set up AWS infrastructure',  'Provision VPC, subnets, RDS, EC2',    'high',   'in_progress', 'DevOps Team',  DATE_ADD(CURDATE(), INTERVAL 3 DAY)),
  ('Design database schema',     'ER diagram and migration scripts',      'high',   'done',        'Backend Lead', DATE_ADD(CURDATE(), INTERVAL 1 DAY)),
  ('Build REST API endpoints',   'CRUD for tasks + auth middleware',      'high',   'in_progress', 'Backend Lead', DATE_ADD(CURDATE(), INTERVAL 5 DAY)),
  ('Implement frontend UI',      'React/HTML dashboard with filters',     'medium', 'in_progress', 'Frontend Dev', DATE_ADD(CURDATE(), INTERVAL 7 DAY)),
  ('Write unit tests',           'Pytest for all API routes',             'medium', 'todo',        'QA Team',      DATE_ADD(CURDATE(), INTERVAL 10 DAY)),
  ('Configure CI/CD pipeline',   'GitHub Actions → EC2 deploy',          'medium', 'todo',        'DevOps Team',  DATE_ADD(CURDATE(), INTERVAL 8 DAY)),
  ('SSL certificate setup',      'ACM cert + HTTPS on ALB',              'high',   'todo',        'DevOps Team',  DATE_ADD(CURDATE(), INTERVAL 4 DAY)),
  ('Performance testing',        'Load test with Locust, target 500 RPS','low',    'todo',        'QA Team',      DATE_ADD(CURDATE(), INTERVAL 14 DAY)),
  ('Documentation',              'README, API docs, runbooks',            'low',    'todo',        NULL,           DATE_ADD(CURDATE(), INTERVAL 20 DAY)),
  ('Security review',            'IAM roles, SGs, secrets manager audit', 'high',  'todo',        'Security Team',DATE_ADD(CURDATE(), INTERVAL 6 DAY));
