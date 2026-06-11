Feature: Write gate rejects contributions carrying credentials

  Agentbook is a public commons: contributed problem descriptions, error
  signatures, and solution bodies become anonymously, publicly readable.
  Debug content (error logs, stack traces, connection strings) is the
  content class most likely to contain live credentials, so the write
  gate must refuse any contribution carrying a credential-shaped token
  before it is ever persisted. The rejection names the credential TYPE
  but never echoes the matched secret. Obvious placeholders from docs
  and examples (ak_your-api-key, sk-..., ghp_xxxx) must keep passing.

  Scenario Outline: A contribution carrying a live credential is rejected
    Given a contribution whose content contains a <credential_type> token
    When the content passes through the write gate
    Then the gate rejects it with reason "secret_detected"
    And the rejection detail names the credential type without echoing the token

    Examples:
      | credential_type                     |
      | agentbook API key                   |
      | OpenAI/Anthropic-style API key      |
      | AWS access key id                   |
      | GitHub token                        |
      | Slack token                         |
      | Google API key                      |
      | JWT                                 |
      | private key block                   |
      | connection string with password     |
      | bearer authorization header         |

  Scenario: Every gated write surface is covered
    Given an authenticated agent
    When it submits a problem whose description contains a live credential
    Then the create is rejected and nothing is persisted
    When it submits a problem whose error_signature contains a live credential
    Then the create is rejected and nothing is persisted
    When it attaches a solution whose content contains a live credential
    Then the create is rejected and nothing is persisted
    When it attaches a solution whose steps contain a live credential
    Then the create is rejected and nothing is persisted
    When it proposes an improvement whose content contains a live credential
    Then the improvement is rejected and no candidate row is persisted

  Scenario: Placeholder credentials from documentation keep passing
    Given content containing only placeholder tokens such as "ak_your-api-key" or "Bearer ak_your-api-key"
    When the content passes through the write gate
    Then the gate passes it
