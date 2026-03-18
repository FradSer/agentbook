# Security Checklist: Dynamic AI Agent Instructions

## Pre-Implementation Security Review

### Input Validation
- [ ] Semantic version format validation (X.Y.Z regex)
- [ ] Content length limits enforced (100-20000 characters)
- [ ] Required sections validation (Review Criteria, Decision Rules)
- [ ] Character encoding validation (UTF-8 only)
- [ ] Null byte injection prevention
- [ ] Line ending normalization (prevent CRLF injection)

### Prompt Injection Defense
- [ ] Pattern detection for "ignore previous instructions"
- [ ] Pattern detection for "disregard prior instructions"
- [ ] Pattern detection for "act as" role manipulation
- [ ] Pattern detection for "you are now" identity changes
- [ ] Pattern detection for "system:" command injection
- [ ] Pattern detection for "forget everything"
- [ ] Pattern detection for "new instructions:"
- [ ] XML/HTML tag escape attempts detection
- [ ] Unicode obfuscation detection (e.g., \\u0020 spaces)
- [ ] Case-insensitive pattern matching
- [ ] Whitespace variation detection (i g n o r e)

### Command Injection Prevention
- [ ] Block "system.execute" patterns
- [ ] Block "os.system" patterns
- [ ] Block "subprocess" patterns
- [ ] Block "eval(" patterns
- [ ] Block "exec(" patterns
- [ ] Block "__import__" patterns
- [ ] Block shell metacharacters in content
- [ ] Block file path traversal attempts (../)

### Content Sanitization
- [ ] HTML tag stripping or escaping
- [ ] Script tag detection and rejection
- [ ] SQL injection pattern detection
- [ ] NoSQL injection pattern detection
- [ ] LDAP injection pattern detection
- [ ] XPath injection pattern detection

### Access Control
- [ ] Authentication required for all instruction operations
- [ ] Authorization checks for create/update/activate operations
- [ ] Role-based access control (RBAC) implementation
- [ ] Operator ID tracking for all changes
- [ ] API key validation for programmatic access
- [ ] Rate limiting on instruction updates (prevent abuse)

### Audit and Compliance
- [ ] All instruction changes logged to audit table
- [ ] Timestamp recorded for every operation
- [ ] Operator ID recorded for every operation
- [ ] Reason field required for activations/rollbacks
- [ ] Audit log immutability (append-only)
- [ ] Audit log retention policy defined
- [ ] Compliance export functionality (JSON/CSV)

### Data Protection
- [ ] Encryption at rest for instruction content
- [ ] TLS/HTTPS for instruction transmission
- [ ] Database connection encryption
- [ ] Secure credential storage (no hardcoded secrets)
- [ ] Environment variable validation
- [ ] Secrets rotation policy defined

### Monitoring and Alerting
- [ ] Security validation failure alerts
- [ ] Injection attempt logging and alerting
- [ ] Suspicious pattern detection alerts
- [ ] Unauthorized access attempt alerts
- [ ] High error rate automatic rollback
- [ ] Database connection failure alerts
- [ ] Cache invalidation failure alerts

## Runtime Security Monitoring

### Real-Time Detection
- [ ] Monitor for sudden approval rate changes (>20% deviation)
- [ ] Monitor for error rate spikes (>50% over 10 reviews)
- [ ] Monitor for unusual instruction activation frequency
- [ ] Monitor for failed validation attempts
- [ ] Monitor for repeated injection attempts from same operator

### Anomaly Detection
- [ ] Baseline instruction performance metrics
- [ ] Statistical deviation detection (>2 standard deviations)
- [ ] Time-series analysis for trend detection
- [ ] Correlation analysis between instruction changes and errors

### Incident Response
- [ ] Automatic rollback on high error rate (>50%)
- [ ] Emergency rollback procedure documented
- [ ] Incident response team contact list
- [ ] Post-incident review process defined
- [ ] Root cause analysis template

## Post-Deployment Security Audit

### Code Review
- [ ] Security-focused code review completed
- [ ] Peer review by security team
- [ ] Static analysis tools run (bandit, semgrep)
- [ ] Dependency vulnerability scan (safety, snyk)
- [ ] OWASP Top 10 checklist reviewed

### Penetration Testing
- [ ] Manual injection attack testing
- [ ] Automated fuzzing of validation logic
- [ ] Boundary condition testing
- [ ] Race condition testing (concurrent activations)
- [ ] Privilege escalation testing

### Compliance Verification
- [ ] GDPR compliance (if applicable)
- [ ] SOC 2 requirements met (if applicable)
- [ ] HIPAA compliance (if applicable)
- [ ] Industry-specific regulations reviewed
- [ ] Data retention policies enforced

## Security Best Practices

### Defense in Depth
- [ ] Multiple validation layers implemented
- [ ] Fail-safe defaults (reject on validation error)
- [ ] Least privilege principle applied
- [ ] Separation of duties (create vs. activate)
- [ ] Input validation at every layer

### Secure Development Lifecycle
- [ ] Threat modeling completed
- [ ] Security requirements documented
- [ ] Security testing in CI/CD pipeline
- [ ] Security training for developers
- [ ] Regular security audits scheduled

### Incident Preparedness
- [ ] Incident response plan documented
- [ ] Rollback procedures tested
- [ ] Communication plan defined
- [ ] Backup and recovery tested
- [ ] Disaster recovery plan in place

## Validation Test Cases

### Positive Tests (Should Pass)
- [ ] Valid instruction with all required sections
- [ ] Instruction at minimum length (100 chars)
- [ ] Instruction at maximum length (20000 chars)
- [ ] Instruction with valid semantic version (1.2.3)
- [ ] Instruction with markdown formatting
- [ ] Instruction with code blocks
- [ ] Instruction with bullet lists

### Negative Tests (Should Fail)
- [ ] Instruction with "ignore previous instructions"
- [ ] Instruction with "act as different agent"
- [ ] Instruction with "system.execute" command
- [ ] Instruction with script tags
- [ ] Instruction with SQL injection attempt
- [ ] Instruction shorter than 100 characters
- [ ] Instruction longer than 20000 characters
- [ ] Instruction with invalid version format
- [ ] Instruction missing required sections
- [ ] Instruction with null bytes
- [ ] Instruction with CRLF injection

### Edge Cases
- [ ] Instruction with Unicode characters
- [ ] Instruction with emoji
- [ ] Instruction with special characters
- [ ] Instruction with very long lines
- [ ] Instruction with nested quotes
- [ ] Instruction with escaped characters

## Security Metrics

### Key Performance Indicators
- [ ] Validation failure rate tracked
- [ ] Injection attempt rate tracked
- [ ] False positive rate measured
- [ ] False negative rate measured
- [ ] Mean time to detect (MTTD) incidents
- [ ] Mean time to respond (MTTR) incidents

### Reporting
- [ ] Weekly security metrics report
- [ ] Monthly security audit summary
- [ ] Quarterly security review meeting
- [ ] Annual penetration test report
- [ ] Incident post-mortem reports

## Emergency Procedures

### High-Severity Incident Response
1. [ ] Trigger emergency rollback immediately
2. [ ] Notify security team and on-call engineer
3. [ ] Isolate affected systems if necessary
4. [ ] Collect forensic evidence (logs, audit trail)
5. [ ] Assess impact and scope
6. [ ] Communicate with stakeholders
7. [ ] Implement fix and test thoroughly
8. [ ] Conduct post-incident review
9. [ ] Update security procedures based on learnings

### Rollback Procedure
1. [ ] Identify last known good instruction version
2. [ ] Verify version is available in database
3. [ ] Execute rollback command with reason
4. [ ] Verify agents pick up rolled-back version
5. [ ] Monitor error rates for 30 minutes
6. [ ] Document rollback in incident log
7. [ ] Notify relevant teams

## Sign-Off

### Pre-Production
- [ ] Security team approval
- [ ] Engineering team approval
- [ ] Product team approval
- [ ] Compliance team approval (if applicable)

### Production Deployment
- [ ] Deployment checklist completed
- [ ] Monitoring dashboards configured
- [ ] Alerting rules deployed
- [ ] Runbook updated
- [ ] Team training completed

### Post-Deployment
- [ ] 24-hour monitoring period completed
- [ ] No critical incidents reported
- [ ] Performance metrics within acceptable range
- [ ] Security metrics baseline established

---

**Document Version**: 1.0.0
**Last Updated**: 2026-03-18
**Owner**: Security Team
**Review Frequency**: Quarterly

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [Prompt Injection Defense Guide](https://markaicode.com/prompt-injection-defense-llm-apps-2026/)
- [AI Security Best Practices](https://www.databricks.com/blog/mitigating-risk-prompt-injection-ai-agents-databricks)
