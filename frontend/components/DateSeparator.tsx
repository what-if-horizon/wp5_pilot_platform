interface DateSeparatorProps {
  label: string
}

export default function DateSeparator({ label }: DateSeparatorProps) {
  return (
    <div className="flex justify-center my-3">
      <span className="bg-date-pill text-date-pill-text text-[12px] px-3 py-1.5 rounded-lg shadow-sm font-medium">
        {label}
      </span>
    </div>
  )
}
