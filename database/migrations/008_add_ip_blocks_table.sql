-- Create ip_blocks table for tracking and blocking IPs attempting admin attacks
CREATE TABLE IF NOT EXISTS ip_blocks (
    id SERIAL PRIMARY KEY,
    ip_address VARCHAR(45) UNIQUE NOT NULL,
    reason VARCHAR(100) NOT NULL,
    attempt_count INTEGER DEFAULT 0,
    first_attempt TIMESTAMP,
    blocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_ip_active ON ip_blocks(ip_address, is_active);
CREATE INDEX IF NOT EXISTS idx_expires_at ON ip_blocks(expires_at);
