Feature: Production deployment honours X-Forwarded-For

  Production runs behind Railway's edge proxy. Without uvicorn's
  --proxy-headers flag, slowapi's get_remote_address resolves to the
  proxy's IP and every anonymous caller collapses into one global
  rate-limit bucket. The Railway start command MUST pass
  --proxy-headers --forwarded-allow-ips=* so the client tier of the
  X-Forwarded-For chain reaches the limiter intact.

  Scenario: ProxyHeadersMiddleware exposes the client IP, not the proxy
    Given the ASGI app is wrapped with uvicorn's ProxyHeadersMiddleware
    And the trusted proxies list is "*"
    When a request arrives with X-Forwarded-For "203.0.113.7, 10.0.0.1"
    Then slowapi.get_remote_address returns "203.0.113.7"

  Scenario: Without ProxyHeadersMiddleware the proxy IP wins
    Given the ASGI app is NOT wrapped with ProxyHeadersMiddleware
    When a request arrives with X-Forwarded-For "203.0.113.7, 10.0.0.1"
    Then slowapi.get_remote_address returns the direct client IP

  Scenario: Railway start command carries the required flags
    Given railway.toml's [deploy] startCommand
    Then it contains "--proxy-headers"
    And it contains "--forwarded-allow-ips=*"
