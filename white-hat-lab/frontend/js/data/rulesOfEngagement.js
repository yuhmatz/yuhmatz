// Rules of Engagement content. Kept as data so the platform is easy to extend
// with new modules without touching view logic.

export const rulesOfEngagement = [
  {
    icon: '📝',
    title: 'Explicit Authorization',
    body:
      'Never test a system without written, signed permission from the owner. Authorization defines what you are allowed to do and protects both you and the client legally. "I thought it was okay" is not a defense — get it in writing first, every time.'
  },
  {
    icon: '🎯',
    title: 'Scope Definition',
    body:
      'Agree in advance exactly which hosts, IP ranges, domains, applications, and techniques are in scope. Anything not explicitly listed is out of scope. Straying outside the agreed boundary — even accidentally — can be illegal and destroys trust.'
  },
  {
    icon: '🔔',
    title: 'Responsible Disclosure',
    body:
      'When you find a vulnerability, report it privately to the owner and give them reasonable time to remediate before any public disclosure. The goal is to reduce risk, never to embarrass, extort, or grandstand.'
  },
  {
    icon: '🛟',
    title: 'Safety First (Do No Harm)',
    body:
      'Avoid actions that could damage data, degrade availability, or disrupt operations. Prefer non-destructive proofs of concept. If a test could cause an outage (e.g. DoS), it must be explicitly authorized, scheduled, and coordinated.'
  },
  {
    icon: '⚖️',
    title: 'Legal Considerations',
    body:
      'Understand the laws that apply to you and your target (e.g. the CFAA in the US, the Computer Misuse Act in the UK, GDPR for personal data). Unauthorized access is a crime in virtually every jurisdiction. When unsure, consult legal counsel — not a forum.'
  },
  {
    icon: '🔒',
    title: 'Data Handling & Confidentiality',
    body:
      'Treat everything you access as confidential. Minimize the data you touch, store findings securely (encrypted), and destroy sensitive data when the engagement ends. Never exfiltrate more than you need to prove impact.'
  },
  {
    icon: '🚫',
    title: 'Never Attack Without Permission',
    body:
      'This lab exists so you can practise safely on systems you control. Skills learned here are for defending and for authorized testing only. Turning them on systems you do not own is unethical and illegal — full stop.'
  }
];

// A short pre-engagement checklist reinforcing the rules above.
export const engagementChecklist = [
  'Signed authorization / statement of work in hand',
  'Scope (targets, techniques, timing) documented and agreed',
  'Emergency contacts and a "stop test" signal established',
  'Rules for handling any discovered sensitive data agreed',
  'Test window and rate limits agreed to avoid outages',
  'Reporting format and disclosure timeline agreed'
];
