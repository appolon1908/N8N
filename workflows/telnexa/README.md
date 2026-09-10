# Telnexa workflow pack

Telnexa automations governed as a pack in this canonical repository.

n8n never connects directly to Telnexa or Jasmin. SMS delivery remains a separately authorized Middleware capability and is not enabled by the observability email integration. SMS rejection and failure events may be observed through the governed Middleware event path without enabling outbound SMS.
