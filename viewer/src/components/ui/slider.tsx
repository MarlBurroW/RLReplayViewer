import * as React from "react";
import { cn } from "../../lib/utils";

interface SliderProps {
  className?: string;
  min?: number;
  max?: number;
  step?: number;
  value?: number[];
  onValueChange?: (value: number[]) => void;
}

const Slider = React.forwardRef<HTMLInputElement, SliderProps>(
  ({ className, value, min = 0, max = 100, step = 1, onValueChange, ...props }, ref) => {
    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const newValue = Number(e.target.value);
      onValueChange?.([newValue]);
    };

    return (
      <input
        type="range"
        ref={ref}
        value={value?.[0] || min}
        min={min}
        max={max}
        step={step}
        onChange={handleChange}
        className={cn(
          "w-full h-2 bg-primary/20 rounded-lg appearance-none cursor-pointer",
          className
        )}
        {...props}
      />
    );
  }
);

Slider.displayName = "Slider";

export { Slider }; 