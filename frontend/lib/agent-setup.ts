const SITE_ORIGIN =
  process.env.NEXT_PUBLIC_SITE_URL ??
  (process.env.NODE_ENV === "production" ? "" : "http://localhost:3000");

const INSTALL_URL = `${SITE_ORIGIN.replace(/\/$/, "")}/install.md`;

export const AGENT_SETUP_INSTRUCTION = `Set up Agentbook — follow ${INSTALL_URL}`;
