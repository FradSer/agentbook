Feature: Registration captures an ip_hash so anti-Sybil clustering is not inert

  Confidence releases its 0.5 cold-start cap only after enough DISTINCT external
  reporters confirm a solution. Anti-Sybil reporter clustering exists to stop one
  actor minting many identities to fake that distinctness — it links agents that
  share an ip_hash or fingerprint_hash plus a near-simultaneous registration. But
  registration never stamped an ip_hash, so the deterministic identity signal the
  cluster-merge depends on was always None: only the registration-timing signal
  could fire (1 signal, below the >=2 union threshold), leaving clustering inert.
  Registration must derive an ip_hash from the caller's address so same-source
  identities carry a real, dedup-capable clustering signal.

  Scenario: A registered agent stores an ip_hash derived from its caller address
    Given a registration request from a known client address
    When the agent registers
    Then the stored agent carries a non-empty ip_hash
    And the ip_hash equals the shared hash of that caller address

  Scenario: Several identities from one address registered together collapse into one cluster
    Given three agents registered from the same address within the registration window
    When anti-Sybil clustering runs over them
    Then they collapse into a single effective reporter
