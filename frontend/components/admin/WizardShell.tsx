"use client"

import { useState } from "react"
import type { AdminTheme } from "./AdminPanel"

const STEP_LABELS = [
  "Experiment",
  "Session",
  "LLM Pipeline",
  "Treatments",
  "Tokens",
  "Review",
]

interface WizardShellProps {
  step: number
  setStep: (step: number) => void
  onSave: () => void
  saving: boolean
  onBack?: () => void
  theme: AdminTheme
  onToggleTheme: () => void
  validateStep?: (step: number) => string | null
  children: React.ReactNode
}

export default function WizardShell({
  step,
  setStep,
  onSave,
  saving,
  onBack,
  theme,
  onToggleTheme,
  validateStep,
  children,
}: WizardShellProps) {
  const totalSteps = STEP_LABELS.length
  const isLast = step === totalSteps - 1
  const [stepError, setStepError] = useState<string | null>(null)
  const [showConfirm, setShowConfirm] = useState(false)

  const tryAdvance = (target: number) => {
    // Allow going back freely
    if (target < step) {
      setStepError(null)
      setStep(target)
      return
    }
    // Validate all steps between current and target
    if (validateStep) {
      for (let s = step; s < target; s++) {
        const err = validateStep(s)
        if (err) {
          setStepError(err)
          setStep(s)
          return
        }
      }
    }
    setStepError(null)
    setStep(target)
  }

  const handleSaveClick = () => {
    if (validateStep) {
      // Validate all steps before saving
      for (let s = 0; s < totalSteps; s++) {
        const err = validateStep(s)
        if (err) {
          setStepError(err)
          setStep(s)
          return
        }
      }
    }
    setStepError(null)
    setShowConfirm(true)
  }

  const handleConfirmSave = () => {
    setShowConfirm(false)
    onSave()
  }

  return (
    <div className="min-h-dvh bg-admin-bg">
      {/* Header */}
      <div className="bg-admin-surface border-b border-admin-border px-6 py-4 flex items-center justify-between">
        <h1 className="text-lg font-medium text-admin-text">Experiment Configuration</h1>
        <div className="flex items-center gap-2">
          {/* Theme toggle */}
          <button
            onClick={onToggleTheme}
            className="p-1.5 rounded-lg bg-admin-raised hover:bg-admin-border text-admin-muted hover:text-admin-text transition-colors"
            aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
            title={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
          >
            {theme === "light" ? (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
              </svg>
            ) : (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
            )}
          </button>
          {onBack && (
            <button
              onClick={onBack}
              className="px-4 py-2 text-sm font-medium bg-admin-raised hover:bg-admin-border text-admin-muted rounded-lg transition-colors"
            >
              Back to Dashboard
            </button>
          )}
        </div>
      </div>

      {/* Step indicator */}
      <div className="bg-admin-surface border-b border-admin-border px-6 py-4">
        <div className="max-w-4xl mx-auto flex items-center gap-1">
          {STEP_LABELS.map((label, i) => (
            <div key={label} className="flex items-center gap-1 flex-1">
              <button
                onClick={() => tryAdvance(i)}
                className={`flex items-center gap-2 text-xs font-medium transition-colors ${
                  i === step
                    ? "text-admin-accent"
                    : i < step
                    ? "text-admin-pastel-green-text hover:opacity-80"
                    : "text-admin-faint"
                }`}
              >
                <span
                  className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-colors ${
                    i === step
                      ? "border-admin-accent bg-admin-accent text-white"
                      : i < step
                      ? "border-admin-pastel-green-text/50 bg-admin-pastel-green text-admin-pastel-green-text"
                      : "border-admin-border text-admin-faint"
                  }`}
                >
                  {i < step ? "\u2713" : i + 1}
                </span>
                <span className="hidden sm:inline">{label}</span>
              </button>
              {i < totalSteps - 1 && (
                <div
                  className={`flex-1 h-0.5 mx-1 rounded ${
                    i < step ? "bg-admin-pastel-green" : "bg-admin-border"
                  }`}
                />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Step content */}
      <div className="max-w-4xl mx-auto px-6 py-6">
        {/* Validation error banner */}
        {stepError && (
          <div className="mb-4 rounded-lg border border-red-400/40 bg-red-500/10 px-4 py-3 flex items-start gap-2">
            <svg className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
            <p className="text-sm text-red-500 font-medium">{stepError}</p>
          </div>
        )}
        {children}
      </div>

      {/* Navigation */}
      <div className="fixed bottom-0 left-0 right-0 bg-admin-surface border-t border-admin-border px-6 py-3 z-20">
        <div className="max-w-4xl mx-auto flex justify-between items-center">
          <button
            onClick={() => tryAdvance(step - 1)}
            disabled={step === 0}
            className="px-4 py-2 text-sm font-medium text-admin-muted hover:text-admin-text disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            Back
          </button>
          <div className="flex items-center gap-3">
            {!isLast && (
              <button
                onClick={() => tryAdvance(step + 1)}
                className="px-5 py-2 text-sm font-medium bg-admin-accent text-white rounded-lg hover:bg-admin-accent-hover transition-colors"
              >
                Next
              </button>
            )}
            {isLast && (
              <button
                onClick={handleSaveClick}
                disabled={saving}
                className="px-5 py-2 text-sm font-medium bg-admin-pastel-green text-admin-pastel-green-text rounded-lg hover:opacity-80 disabled:opacity-50 transition-colors font-semibold"
              >
                {saving ? "Saving..." : "Save & Lock Configuration"}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Save confirmation modal */}
      {showConfirm && (
        <div className="fixed inset-0 flex items-center justify-center bg-black/40 z-50">
          <div className="bg-admin-surface rounded-xl shadow-lg border border-admin-border p-6 max-w-md mx-4 space-y-4">
            <h3 className="text-base font-semibold text-admin-text">Confirm Save</h3>
            <p className="text-sm text-admin-muted">
              Once saved, this experiment configuration <span className="font-semibold text-admin-text">cannot be modified</span>.
              To make changes you will need to create a new experiment.
            </p>
            <p className="text-sm text-admin-muted">
              Are you sure you want to save and lock this configuration?
            </p>
            <div className="flex justify-end gap-3 pt-1">
              <button
                onClick={() => setShowConfirm(false)}
                className="px-4 py-2 text-sm font-medium text-admin-muted hover:text-admin-text transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmSave}
                className="px-5 py-2 text-sm font-medium bg-admin-pastel-green text-admin-pastel-green-text rounded-lg hover:opacity-80 transition-colors font-semibold"
              >
                Save & Lock
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
