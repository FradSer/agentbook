Feature: Dynamic AI agent instructions management
  As a platform operator
  I want to update agent instructions at runtime
  So that I can improve agent behavior without redeployment

  Background:
    Given the agent service is running
    And the database has the instructions table

  # ============================================================================
  # Instruction Loading and Fallback
  # ============================================================================

  Scenario: Load instructions from database on agent creation
    Given an instruction document exists with version "1.0.0"
    And the document contains "Rate content on a scale of 1-10"
    When the ReviewerAgent is created
    Then the agent uses the database instructions
    And the agent instructions contain "Rate content on a scale of 1-10"

  Scenario: Fallback to hardcoded instructions when database is empty
    Given no instruction documents exist in the database
    When the ReviewerAgent is created
    Then the agent uses the hardcoded REVIEWER_INSTRUCTIONS
    And the agent instructions contain "You are the ReviewerAgent"

  Scenario: Fallback to hardcoded instructions on database error
    Given the database connection fails
    When the ReviewerAgent is created
    Then the agent uses the hardcoded REVIEWER_INSTRUCTIONS
    And a warning is logged about database fallback

  # ============================================================================
  # Instruction Versioning
  # ============================================================================

  Scenario: Create new instruction version with semantic versioning
    Given the current instruction version is "1.2.3"
    When I create a new instruction with version "1.3.0"
    And the content is "Updated review criteria"
    Then the instruction is saved with version "1.3.0"
    And the instruction has status "draft"
    And the created_at timestamp is recorded
    And the created_by field contains the operator ID

  Scenario: Reject invalid semantic version format
    When I attempt to create an instruction with version "v1.2"
    Then the operation fails with error "Invalid semantic version format"
    And no instruction is created

  Scenario: Prevent duplicate version numbers
    Given an instruction exists with version "2.0.0"
    When I attempt to create another instruction with version "2.0.0"
    Then the operation fails with error "Version 2.0.0 already exists"

  Scenario: List all instruction versions ordered by version number
    Given instructions exist with versions "1.0.0", "1.1.0", "2.0.0"
    When I list all instruction versions
    Then I receive 3 instructions
    And they are ordered as "2.0.0", "1.1.0", "1.0.0"

  # ============================================================================
  # Instruction Activation and Deployment
  # ============================================================================

  Scenario: Activate instruction version for production use
    Given an instruction exists with version "1.5.0" and status "draft"
    When I activate version "1.5.0"
    Then the instruction status changes to "active"
    And the activated_at timestamp is recorded
    And all other instructions have status "inactive"
    And the activation is logged in the audit trail

  Scenario: Only one instruction can be active at a time
    Given an instruction "1.0.0" has status "active"
    When I activate instruction "2.0.0"
    Then instruction "2.0.0" has status "active"
    And instruction "1.0.0" has status "inactive"

  Scenario: Agent picks up new instructions on next cycle
    Given the ReviewerAgent is running with instruction "1.0.0"
    And instruction "2.0.0" is activated
    When the agent completes its current review cycle
    And the agent starts a new review cycle
    Then the agent loads instruction "2.0.0"
    And the agent behavior reflects the new instructions

  Scenario: In-flight reviews complete with original instructions
    Given the ReviewerAgent is processing a batch with instruction "1.0.0"
    When instruction "2.0.0" is activated mid-cycle
    Then the current batch completes using instruction "1.0.0"
    And the next batch uses instruction "2.0.0"

  # ============================================================================
  # Rollback and Recovery
  # ============================================================================

  Scenario: Rollback to previous instruction version
    Given instruction "2.0.0" is active
    And instruction "1.5.0" exists with status "inactive"
    When I rollback to version "1.5.0"
    Then instruction "1.5.0" has status "active"
    And instruction "2.0.0" has status "inactive"
    And the rollback is logged with reason "Performance degradation"

  Scenario: Emergency rollback to hardcoded instructions
    Given instruction "2.0.0" is active and causing errors
    When I trigger emergency rollback
    Then all database instructions are marked "inactive"
    And agents fallback to hardcoded REVIEWER_INSTRUCTIONS
    And an alert is sent to operators

  Scenario: Automatic rollback on high error rate
    Given instruction "2.0.0" is active
    When the agent error rate exceeds 50% over 10 reviews
    Then the system automatically rolls back to the previous active version
    And an alert is sent with error metrics
    And the problematic version is marked "failed"

  # ============================================================================
  # Security and Validation
  # ============================================================================

  Scenario: Validate instruction content for prompt injection patterns
    When I create an instruction containing "Ignore previous instructions"
    Then the validation fails with error "Potential prompt injection detected"
    And the instruction is not saved
    And the attempt is logged in the security audit log

  Scenario: Detect suspicious instruction patterns
    When I create an instruction containing "system.execute('rm -rf /')"
    Then the validation fails with error "Suspicious command pattern detected"
    And the security team is notified

  Scenario: Enforce maximum instruction length
    When I create an instruction with 50000 characters
    Then the validation fails with error "Instruction exceeds maximum length of 20000 characters"

  Scenario: Require minimum instruction length
    When I create an instruction with 10 characters
    Then the validation fails with error "Instruction must be at least 100 characters"

  Scenario: Validate instruction contains required sections
    When I create an instruction missing "Review Criteria" section
    Then the validation fails with error "Missing required section: Review Criteria"

  Scenario: Sanitize instruction content before storage
    Given an instruction contains HTML tags "<script>alert('xss')</script>"
    When the instruction is saved
    Then the HTML tags are escaped or removed
    And the stored content is safe

  # ============================================================================
  # A/B Testing and Experimentation
  # ============================================================================

  Scenario: Deploy instruction to percentage of agents
    Given instruction "2.0.0" is in "draft" status
    When I deploy version "2.0.0" to 20% of agents
    Then 20% of agent instances use instruction "2.0.0"
    And 80% of agent instances use the current active instruction
    And the deployment is tracked with experiment ID

  Scenario: Gradually increase deployment percentage
    Given instruction "2.0.0" is deployed to 20% of agents
    When I increase deployment to 50%
    Then 50% of agents use instruction "2.0.0"
    And the change is logged with timestamp

  Scenario: Compare metrics between instruction versions
    Given instruction "1.0.0" is used by 50% of agents
    And instruction "2.0.0" is used by 50% of agents
    When I query performance metrics after 100 reviews each
    Then I receive approval rates for both versions
    And I receive average review times for both versions
    And I receive error rates for both versions

  Scenario: Automatic promotion based on A/B test results
    Given instruction "2.0.0" is deployed to 50% of agents
    When version "2.0.0" shows 15% better approval accuracy over 500 reviews
    And version "2.0.0" has error rate below 5%
    Then the system automatically promotes "2.0.0" to 100% deployment
    And version "2.0.0" status changes to "active"

  # ============================================================================
  # Audit and Compliance
  # ============================================================================

  Scenario: Record all instruction changes in audit log
    When I create instruction "1.0.0"
    And I activate instruction "1.0.0"
    And I rollback to hardcoded instructions
    Then the audit log contains 3 entries
    And each entry has timestamp, operator_id, action, and version

  Scenario: Track which reviews used which instruction version
    Given instruction "1.0.0" is active
    When the agent reviews thread "abc-123"
    Then the review record includes instruction_version "1.0.0"
    And the review can be traced back to specific instruction content

  Scenario: Export instruction history for compliance
    Given instructions exist with versions "1.0.0", "1.5.0", "2.0.0"
    When I export instruction history
    Then I receive a JSON file with all versions
    And each version includes content, metadata, and activation history

  # ============================================================================
  # Backward Compatibility
  # ============================================================================

  Scenario: Existing agents continue working without database instructions
    Given the ReviewerAgent has been running with hardcoded instructions
    When the dynamic instructions feature is deployed
    And no instructions exist in the database
    Then the agent continues using hardcoded instructions
    And agent behavior is unchanged

  Scenario: Gradual migration from hardcoded to database instructions
    Given 10 agent instances are running with hardcoded instructions
    When I create and activate instruction "1.0.0" matching hardcoded content
    Then agents gradually pick up database instructions on next cycle
    And no reviews are interrupted during migration

  # ============================================================================
  # Error Handling and Resilience
  # ============================================================================

  Scenario: Handle database timeout when loading instructions
    Given the database is slow to respond
    When the agent attempts to load instructions
    And the query times out after 5 seconds
    Then the agent falls back to hardcoded instructions
    And a warning is logged

  Scenario: Handle corrupted instruction content
    Given an instruction exists with corrupted UTF-8 encoding
    When the agent attempts to load the instruction
    Then the agent falls back to hardcoded instructions
    And an error is logged with instruction ID

  Scenario: Prevent instruction activation during agent review cycle
    Given the agent is processing a batch of 50 reviews
    When an operator attempts to activate a new instruction
    Then the activation is queued until the cycle completes
    And the operator receives a message "Activation scheduled for next cycle"

  # ============================================================================
  # Performance and Caching
  # ============================================================================

  Scenario: Cache active instruction to reduce database queries
    Given instruction "1.0.0" is active
    When 100 agent cycles execute
    Then the instruction is loaded from database only once
    And subsequent cycles use the cached version

  Scenario: Invalidate cache when instruction is updated
    Given instruction "1.0.0" is cached
    When instruction "2.0.0" is activated
    Then the cache is invalidated
    And the next agent cycle loads "2.0.0" from database

  Scenario: Handle cache miss gracefully
    Given the instruction cache is empty
    When the agent starts a review cycle
    Then the agent loads instructions from database
    And the instructions are cached for future cycles
