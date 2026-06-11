interface SystemMessageProps {
  content: string;
}

export default function SystemMessage({ content }: SystemMessageProps) {
  return (
    <div className="flex justify-center my-3">
      <span className="text-xs text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-400/10 border border-amber-200 dark:border-amber-400/20 rounded-full px-3 py-1 font-medium">
        {content}
      </span>
    </div>
  );
}
