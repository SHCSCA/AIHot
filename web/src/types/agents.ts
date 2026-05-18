export interface AgentDefinition {
  id: string;
  name: string;
  emoji: string;
  color: string;
  description: string;
  system: string;
  toolNames?: string[];
  category: string;
  domain: string;
  capabilities: string[];
  body: string;
}

export interface AgentCategory {
  id: string;
  label: string;
  emoji: string;
}