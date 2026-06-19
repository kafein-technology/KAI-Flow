import React, { useState } from "react";
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

  return (
    <div className="relative w-full">
      <input
        {...field}
        type={visible ? "text" : "password"}
        placeholder={placeholder}
        autoComplete="new-password"
        className={`${className} !pr-12`}
      />
      <button
        type="button"
        tabIndex={-1}
        onMouseDown={(e) => {
          e.preventDefault();
          setVisible((prev) => !prev);
        }}
        className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-gray-500 hover:text-gray-700 transition-colors duration-200"
        aria-label={visible ? "Hide password" : "Show password"}
      >
        {visible ? (
          <EyeOff className="w-4 h-4 shrink-0" />
        ) : (
          <Eye className="w-4 h-4 shrink-0" />
        )}
      </button>
    </div>
  );
};

export default CredentialPasswordField;
