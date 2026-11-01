import { useState } from "react";
import { Input } from "../ui/Input";
import { Icon } from "../ui/Icon";
import { useDebouncedCallback } from "../../lib/useDebouncedCallback";

export interface SearchInputProps {
  /** The committed value from the URL. Seeds the box on first mount. */
  value: string;
  onCommit: (value: string) => void;
  label: string;
  placeholder?: string;
  delayMs?: number;
}

/**
 * The box keeps its own instant state and pushes to the URL on a 300ms pause.
 * Driving the input straight from the query string would make every keystroke
 * a navigation and a request, and the caret would fight the re-render.
 */
export function SearchInput({
  value,
  onCommit,
  label,
  placeholder = "Search…",
  delayMs = 300,
}: SearchInputProps) {
  const [text, setText] = useState(value);
  const commit = useDebouncedCallback(onCommit, delayMs);

  // Someone else cleared the filters: follow the URL back down.
  const [lastExternal, setLastExternal] = useState(value);
  if (value !== lastExternal) {
    setLastExternal(value);
    setText(value);
  }

  return (
    <div className="relative">
      <Icon
        name="search"
        size={15}
        className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-2"
      />
      <Input
        type="search"
        aria-label={label}
        placeholder={placeholder}
        className="pl-9"
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          commit(e.target.value);
        }}
      />
    </div>
  );
}
