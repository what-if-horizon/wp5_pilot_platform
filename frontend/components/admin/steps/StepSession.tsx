"use client"

import type { SimulationConfig } from "../../../lib/admin-types"

interface StepSessionProps {
  config: SimulationConfig
  onChange: (updates: Partial<SimulationConfig>) => void
  touched: boolean
}

const inputClass = "w-full px-3 py-2 border border-admin-border rounded-lg text-sm bg-admin-surface text-admin-text focus:outline-none focus:border-admin-accent focus:ring-1 focus:ring-admin-accent/30"

export default function StepSession({ config, onChange, touched }: StepSessionProps) {
  const updateAgentName = (index: number, value: string) => {
    const names = [...config.agent_names]
    names[index] = value
    onChange({ agent_names: names })
  }

  const handleNumAgentsChange = (n: number) => {
    const names = [...config.agent_names]
    if (n > names.length) {
      while (names.length < n) names.push("")
    } else {
      names.length = n
    }
    onChange({ num_agents: n, agent_names: names })
  }

  // Validation: check for empty or duplicate names
  const agentNameErrors = config.agent_names.map((name, i) => {
    if (!name.trim()) return "Required"
    if (config.agent_names.some((other, j) => j !== i && other.trim() === name.trim())) return "Duplicate"
    return null
  })

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-admin-text">Session & Agents</h2>
        <p className="text-sm text-admin-muted mt-1">
          Configure session timing, agent count, and message pacing.
        </p>
      </div>

      <div className="bg-admin-surface rounded-lg border border-admin-border p-5 space-y-4">
        <h3 className="text-sm font-semibold text-admin-muted uppercase tracking-wider">Session</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-admin-text mb-1">
              Duration (minutes)
            </label>
            <input
              type="number"
              min={1}
              value={config.session_duration_minutes}
              onChange={(e) => onChange({ session_duration_minutes: Math.max(1, parseInt(e.target.value) || 1) })}
              className={inputClass}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-admin-text mb-1">
              Random seed
            </label>
            <input
              type="number"
              value={config.random_seed}
              onChange={(e) => onChange({ random_seed: parseInt(e.target.value) || 0 })}
              className={inputClass}
            />
          </div>
        </div>
      </div>

      <div className="bg-admin-surface rounded-lg border border-admin-border p-5 space-y-4">
        <h3 className="text-sm font-semibold text-admin-muted uppercase tracking-wider">Agents</h3>
        <div>
          <label className="block text-sm font-medium text-admin-text mb-1">
            Number of agents
          </label>
          <input
            type="number"
            min={0}
            max={20}
            value={config.num_agents}
            onChange={(e) => handleNumAgentsChange(Math.max(0, parseInt(e.target.value) || 0))}
            className="w-24 px-3 py-2 border border-admin-border rounded-lg text-sm bg-admin-surface text-admin-text focus:outline-none focus:border-admin-accent focus:ring-1 focus:ring-admin-accent/30"
          />
        </div>
        {config.num_agents > 0 && (
          <div>
            <label className="block text-sm font-medium text-admin-text mb-2">
              Agent names
            </label>
            <div className="flex flex-wrap gap-2">
              {config.agent_names.map((name, i) => (
                <div key={i} className="flex flex-col">
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => updateAgentName(i, e.target.value)}
                    placeholder={`Agent ${i + 1}`}
                    className={`w-32 px-3 py-1.5 border rounded-lg text-sm bg-admin-surface text-admin-text focus:outline-none focus:ring-1 ${
                      touched && agentNameErrors[i]
                        ? "border-red-400 focus:border-red-400 focus:ring-red-400/30"
                        : "border-admin-border focus:border-admin-accent focus:ring-admin-accent/30"
                    }`}
                  />
                  {touched && agentNameErrors[i] && (
                    <span className="text-xs text-red-400 mt-0.5">{agentNameErrors[i]}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="bg-admin-surface rounded-lg border border-admin-border p-5 space-y-4">
        <h3 className="text-sm font-semibold text-admin-muted uppercase tracking-wider">Pacing</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-admin-text mb-1">
              Messages per minute
            </label>
            <input
              type="number"
              min={0}
              value={config.messages_per_minute}
              onChange={(e) => onChange({ messages_per_minute: Math.max(0, parseInt(e.target.value) || 0) })}
              className={inputClass}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-admin-text mb-1">
              Context window size
            </label>
            <input
              type="number"
              min={1}
              value={config.context_window_size}
              onChange={(e) => onChange({ context_window_size: Math.max(1, parseInt(e.target.value) || 1) })}
              className={inputClass}
            />
            <p className="text-xs text-admin-faint mt-1">Recent messages included in LLM prompts</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-admin-text mb-1">
              Max concurrent agent turns
            </label>
            <input
              type="number"
              min={1}
              value={config.max_concurrent_turns}
              onChange={(e) => onChange({ max_concurrent_turns: Math.max(1, parseInt(e.target.value) || 1) })}
              className={inputClass}
            />
            <p className="text-xs text-admin-faint mt-1">Maximum agents composing messages simultaneously. Higher values create busier, more overlapping conversations</p>
          </div>
        </div>
      </div>
    </div>
  )
}
