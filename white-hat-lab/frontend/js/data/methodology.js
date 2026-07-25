// The ethical hacking methodology, modelled as an ordered lifecycle. Each stage
// carries the fields the spec asks for: description, purpose, tools, outputs,
// and best practices. Stored as data to keep the timeline view generic.

export const methodology = [
  {
    id: 'recon',
    name: 'Reconnaissance',
    icon: '🔍',
    description:
      'Gather information about the target using passive and active techniques. Passive recon uses public sources without touching the target; active recon interacts with it directly.',
    purpose:
      'Build an accurate picture of the attack surface — domains, IPs, technologies, people, and exposed services — before touching anything sensitive.',
    tools: ['whois', 'theHarvester', 'Google dorks', 'Shodan', 'DNS enumeration', 'OSINT'],
    outputs: [
      'List of in-scope domains and IP ranges',
      'Technology stack and hosting details',
      'Potential entry points and exposed assets'
    ],
    bestPractices: [
      'Prefer passive sources first to stay quiet and in scope',
      'Document every source so findings are reproducible',
      'Confirm each asset is actually in scope before probing'
    ]
  },
  {
    id: 'scanning',
    name: 'Scanning',
    icon: '📡',
    description:
      'Actively probe in-scope hosts to discover live systems, open ports, and running services. This is the first hands-on interaction with the target infrastructure.',
    purpose:
      'Map which services are reachable so later phases can focus effort where it matters.',
    tools: ['Nmap', 'masscan', 'recon_scanner.py (this lab)', 'ping/traceroute'],
    outputs: [
      'Open port inventory per host',
      'Detected services and versions',
      'Network topology hints'
    ],
    bestPractices: [
      'Throttle scan speed to avoid disrupting production',
      'Scan only authorized hosts and ports',
      'Save raw scan output as evidence'
    ]
  },
  {
    id: 'enumeration',
    name: 'Enumeration',
    icon: '🗂️',
    description:
      'Dig deeper into discovered services to extract concrete details: usernames, shares, endpoints, directories, banners, and configuration hints.',
    purpose:
      'Turn "a service is running" into "here are the specific, actionable details of that service" — the raw material for finding vulnerabilities.',
    tools: ['gobuster / ffuf', 'enum4linux', 'nikto', 'Burp Suite', 'smbclient'],
    outputs: [
      'Directory and endpoint listings',
      'Valid usernames / accounts',
      'Service banners and version details'
    ],
    bestPractices: [
      'Correlate findings across services',
      'Note default credentials and misconfigurations',
      'Keep meticulous notes — enumeration feeds everything after it'
    ]
  },
  {
    id: 'vuln',
    name: 'Vulnerability Assessment',
    icon: '🧪',
    description:
      'Analyze the enumerated attack surface to identify weaknesses: missing patches, insecure configurations, and flaws such as injection or broken access control.',
    purpose:
      'Produce a prioritized list of vulnerabilities with an initial risk rating, so exploitation effort targets the highest-impact issues.',
    tools: ['OpenVAS / Nessus', 'nuclei', 'OWASP ZAP', 'manual code/logic review', 'CVSS calculator'],
    outputs: [
      'Ranked list of candidate vulnerabilities',
      'Preliminary CVSS scores',
      'Hypotheses to validate through exploitation'
    ],
    bestPractices: [
      'Validate scanner output manually — expect false positives',
      'Score with CVSS for consistent, defensible prioritization',
      'Consider business context, not just technical severity'
    ]
  },
  {
    id: 'exploitation',
    name: 'Exploitation',
    icon: '💥',
    description:
      'Safely confirm a vulnerability by exploiting it to the minimum extent needed to prove impact — for example, bypassing a login or reading a file you should not be able to read.',
    purpose:
      'Move from theoretical to demonstrated risk, giving stakeholders undeniable evidence that a flaw is real and exploitable.',
    tools: ['Metasploit', 'Burp Suite', 'sqlmap', 'custom scripts', 'this lab’s training endpoints'],
    outputs: [
      'Working proof of concept',
      'Evidence (screenshots, request/response captures)',
      'Confirmed impact statement'
    ],
    bestPractices: [
      'Do the least necessary to prove the point — no unnecessary damage',
      'Never pivot outside the agreed scope',
      'Capture clean, reproducible evidence as you go'
    ]
  },
  {
    id: 'post',
    name: 'Post-Exploitation',
    icon: '🧭',
    description:
      'Assess what the confirmed access actually means: what data or systems are now reachable, and how far an attacker could realistically go from here.',
    purpose:
      'Quantify true business impact — the difference between "a bug" and "a breach" — while staying strictly within authorized limits.',
    tools: ['Manual investigation', 'privilege-escalation checks', 'data-access mapping'],
    outputs: [
      'Impact and blast-radius analysis',
      'Evidence of reachable sensitive data or systems',
      'Cleanup notes (artifacts to remove)'
    ],
    bestPractices: [
      'Stay inside authorized boundaries at all times',
      'Do not exfiltrate real sensitive data — prove access, then stop',
      'Restore any changes and remove test artifacts afterward'
    ]
  },
  {
    id: 'documentation',
    name: 'Documentation',
    icon: '🗒️',
    description:
      'Continuously record what you did, how, and what you found — commands, payloads, timestamps, and evidence — throughout the entire engagement.',
    purpose:
      'Ensure every finding is reproducible and defensible. Good notes taken during testing make the final report accurate and fast to write.',
    tools: ['Note-taking tools', 'screenshot capture', 'command logging', 'evidence vault'],
    outputs: [
      'Time-stamped activity log',
      'Organized evidence per finding',
      'Reproduction steps for each issue'
    ],
    bestPractices: [
      'Document as you go, not after the fact',
      'Store evidence securely and confidentially',
      'Tie every claim to concrete, reproducible evidence'
    ]
  },
  {
    id: 'reporting',
    name: 'Reporting',
    icon: '📄',
    description:
      'Deliver a clear, professional report: an executive summary for leadership and detailed, actionable findings for the technical team, each with remediation guidance.',
    purpose:
      'This is the product of the engagement. A vulnerability that is not communicated well never gets fixed — reporting is where security value is actually delivered.',
    tools: ['Report generator (this lab)', 'CVSS calculator', 'templating tools'],
    outputs: [
      'Executive summary and risk overview',
      'Per-finding detail: severity, PoC, impact, remediation',
      'Prioritized remediation roadmap'
    ],
    bestPractices: [
      'Write for two audiences: executives and engineers',
      'Make every finding actionable with concrete fixes',
      'Prioritize by real business risk, not just CVSS'
    ]
  }
];
