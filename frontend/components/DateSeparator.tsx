interface DateSeparatorProps {
  label: string
}

export default function DateSeparator({ label }: DateSeparatorProps) {
  return (
    <div className="flex justify-center my-4">
      <span className="bg-date-pill text-date-pill-text text-[11px] px-3 py-1 rounded-full font-medium tracking-wide uppercase">
        {label}
      </span>
    </div>
  )
}
