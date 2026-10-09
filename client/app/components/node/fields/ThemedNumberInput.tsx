import { ChevronDown, ChevronUp } from "lucide-react";
import { useRef } from "react";
import type { FocusEventHandler } from "react";

interface NumberStepControlsProps {
  onIncrease: () => void;
  onDecrease: () => void;
  increaseDisabled?: boolean;
  decreaseDisabled?: boolean;
  increaseLabel?: string;
  decreaseLabel?: string;
}

export const NumberStepControls = ({
  onIncrease,
  onDecrease,
  increaseDisabled = false,
  decreaseDisabled = false,
  increaseLabel = "Increase value",
  decreaseLabel = "Decrease value",
}: NumberStepControlsProps) => (
  <div className="flex w-7 shrink-0 flex-col border-l border-slate-700">
    <button
      type="button"
      tabIndex={-1}
      aria-label={increaseLabel}
      disabled={increaseDisabled}
      onMouseDown={(event) => event.preventDefault()}
      onClick={onIncrease}
      className="flex min-h-0 flex-1 items-center justify-center text-slate-500 transition-colors hover:bg-blue-500/15 hover:text-blue-300 disabled:pointer-events-none disabled:text-slate-700"
    >
      <ChevronUp size={11} />
    </button>
    <button
      type="button"
      tabIndex={-1}
      aria-label={decreaseLabel}
      disabled={decreaseDisabled}
      onMouseDown={(event) => event.preventDefault()}
      onClick={onDecrease}
      className="flex min-h-0 flex-1 items-center justify-center border-t border-slate-700 text-slate-500 transition-colors hover:bg-blue-500/15 hover:text-blue-300 disabled:pointer-events-none disabled:text-slate-700"
    >
      <ChevronDown size={11} />
    </button>
  </div>
);

interface ThemedNumberInputProps {
  value?: number | string | null;
  onChange: (value: string) => void;
  name?: string;
  min?: number;
  max?: number;
  step?: number;
  placeholder?: string;
  disabled?: boolean;
  ariaLabel?: string;
  onBlur?: FocusEventHandler<HTMLInputElement>;
  size?: "default" | "compact";
  className?: string;
}

export const ThemedNumberInput = ({
  value,
  onChange,
  name,
  min,
  max,
  step = 1,
  placeholder,
  disabled = false,
  ariaLabel,
  onBlur,
  size = "default",
  className = "w-full",
}: ThemedNumberInputProps) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const currentValue = value ?? "";
  const numericValue = currentValue === "" ? null : Number(currentValue);
  const hasNumericValue = numericValue !== null && Number.isFinite(numericValue);
  const increaseDisabled =
    disabled || (hasNumericValue && max !== undefined && numericValue >= max);
  const decreaseDisabled =
    disabled || (hasNumericValue && min !== undefined && numericValue <= min);

  const stepValue = (direction: 1 | -1) => {
    const input = inputRef.current;
    if (!input || disabled) return;

    if (direction === 1) input.stepUp();
    else input.stepDown();

    onChange(input.value);
    input.focus();
  };

  const compact = size === "compact";
  const inputSizeClass = compact ? "px-3 py-2" : "px-4 py-3";

  return (
    <div
      className={`${className} flex overflow-hidden rounded-lg border border-slate-600 bg-[#10182c] transition-colors focus-within:border-blue-500 focus-within:ring-1 focus-within:ring-blue-500/20`}
    >
      <input
        ref={inputRef}
        type="number"
        name={name}
        value={currentValue}
        min={min}
        max={max}
        step={step}
        disabled={disabled}
        aria-label={ariaLabel}
        placeholder={placeholder}
        onBlur={onBlur}
        onChange={(event) => onChange(event.target.value)}
        className={`${inputSizeClass} min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-slate-500 disabled:cursor-not-allowed disabled:text-slate-500 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none`}
      />
      <NumberStepControls
        increaseDisabled={increaseDisabled}
        decreaseDisabled={decreaseDisabled}
        increaseLabel={ariaLabel ? `Increase ${ariaLabel.toLowerCase()}` : undefined}
        decreaseLabel={ariaLabel ? `Decrease ${ariaLabel.toLowerCase()}` : undefined}
        onIncrease={() => stepValue(1)}
        onDecrease={() => stepValue(-1)}
      />
    </div>
  );
};

export default ThemedNumberInput;
