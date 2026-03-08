"use client"

import { useState } from "react"
import type { TokenConfig } from "../../../lib/admin-types"
import { generateTokens } from "../../../lib/admin-api"

interface StepTokensProps {
  tokens: TokenConfig
  setTokens: (tokens: TokenConfig) => void
  groupNames: string[]
  adminKey: string
}

export default function StepTokens({
  tokens,
  setTokens,
  groupNames,
  adminKey,
}: StepTokensProps) {
  const [perGroup, setPerGroup] = useState(10)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState("")

  const totalTokens = Object.values(tokens.groups).reduce((sum, arr) => sum + arr.length, 0)

  const handleGenerate = async () => {
    if (groupNames.length === 0) {
      setError("Define treatment groups in Step 4 first")
      return
    }
    setGenerating(true)
    setError("")
    try {
      const result = await generateTokens(adminKey, perGroup, groupNames)
      setTokens({ groups: result.tokens })
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed")
    }
    setGenerating(false)
  }

  const downloadCSV = () => {
    const rows = ["token,treatment_group"]
    for (const [group, toks] of Object.entries(tokens.groups)) {
      for (const t of toks) {
        rows.push(`${t},${group}`)
      }
    }
    const blob = new Blob([rows.join("\n")], { type: "text/csv" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = "participant_tokens.csv"
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-admin-text">Participant Tokens</h2>
        <p className="text-sm text-admin-muted mt-1">
          Generate cryptographically random, single-use tokens for each treatment group.
        </p>
      </div>

      <div className="bg-admin-surface rounded-lg border border-admin-border p-5 space-y-4">
        <div className="flex items-end gap-4">
          <div>
            <label className="block text-sm font-medium text-admin-text mb-1">
              Participants per group
            </label>
            <input
              type="number"
              min={1}
              max={1000}
              value={perGroup}
              onChange={(e) => setPerGroup(Math.max(1, parseInt(e.target.value) || 1))}
              className="w-28 px-3 py-2 border border-admin-border rounded-lg text-sm bg-admin-surface text-admin-text focus:outline-none focus:border-admin-accent focus:ring-1 focus:ring-admin-accent/30"
            />
          </div>
          <button
            onClick={handleGenerate}
            disabled={generating || groupNames.length === 0}
            className="px-5 py-2 text-sm font-medium bg-admin-accent text-white rounded-lg hover:bg-admin-accent-hover disabled:opacity-50 transition-colors"
          >
            {generating ? "Generating..." : "Generate Tokens"}
          </button>
        </div>

        {groupNames.length === 0 && (
          <p className="text-xs text-amber-600">Define treatment groups in Step 4 first.</p>
        )}

        <p className="text-xs text-admin-faint">
          {groupNames.length} group(s) x {perGroup} = {groupNames.length * perGroup} tokens total
        </p>

        {error && <p className="text-sm text-red-500">{error}</p>}
      </div>

      {totalTokens > 0 && (
        <>
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-admin-text">
              {totalTokens} tokens generated ({Object.keys(tokens.groups).length} groups)
            </p>
            <button
              onClick={downloadCSV}
              className="px-4 py-1.5 text-xs font-medium bg-admin-pastel-green text-admin-pastel-green-text rounded-lg hover:opacity-80 transition-colors"
            >
              Download CSV
            </button>
          </div>

          <div className="bg-admin-surface rounded-lg border border-admin-border overflow-hidden">
            <div className="max-h-80 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="bg-admin-raised sticky top-0">
                  <tr>
                    <th className="text-left px-4 py-2 text-xs font-semibold text-admin-muted uppercase">Group</th>
                    <th className="text-left px-4 py-2 text-xs font-semibold text-admin-muted uppercase">Tokens</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(tokens.groups).map(([group, toks]) => (
                    <tr key={group} className="border-t border-admin-border">
                      <td className="px-4 py-2 font-mono text-xs text-admin-text align-top whitespace-nowrap">
                        {group}
                        <span className="text-admin-faint ml-1">({toks.length})</span>
                      </td>
                      <td className="px-4 py-2">
                        <div className="flex flex-wrap gap-1">
                          {toks.slice(0, 20).map((t) => (
                            <span
                              key={t}
                              className="inline-block px-2 py-0.5 bg-admin-raised rounded text-xs font-mono text-admin-muted border border-admin-border"
                            >
                              {t}
                            </span>
                          ))}
                          {toks.length > 20 && (
                            <span className="text-xs text-admin-faint">+{toks.length - 20} more</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
