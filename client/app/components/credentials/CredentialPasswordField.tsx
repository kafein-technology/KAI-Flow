import React, { useState, useRef } from "react";
import { useField } from "formik";
import { Eye, EyeOff } from "lucide-react";

interface CredentialPasswordFieldProps {
  name: string;
  placeholder?: string;
  className?: string;
}

const CredentialPasswordField: React.FC<CredentialPasswordFieldProps> = ({
  name,
  placeholder,
  className = "",
}) => {
  const [field] = useField(name);
  const [visible, setVisible] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const toggleVisibility = () => {
    setVisible((prev) => !prev);
    // Keep focus on input element when toggling
    if (inputRef.current) {
      setTimeout(() => {
        inputRef.current?.focus();
      }, 0);
    }
  };

  return (
    <div className="relative w-full">
      <input
        {...field}
        ref={inputRef}
        type={visible ? "text" : "password"}
        placeholder={placeholder}
        autoComplete="new-password"
        className={`${className} !pr-12`}
      />
      <button
        type="button"
        onClick={toggleVisibility}
        className="absolute inset-y-0 right-0 z-10 flex w-11 items-center justify-center text-gray-500 hover:text-gray-700 transition-colors duration-200 cursor-pointer focus:outline-none focus:text-blue-600"
        aria-label={visible ? "Hide password" : "Show password"}
      >
        {visible ? (
          <EyeOff className="w-4 h-4 shrink-0 pointer-events-none" />
        ) : (
          <Eye className="w-4 h-4 shrink-0 pointer-events-none" />
        )}
      </button>
    </div>
  );
};

export default CredentialPasswordField;
