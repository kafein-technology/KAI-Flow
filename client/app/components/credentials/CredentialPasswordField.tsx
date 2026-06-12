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

  const handleCopy = (e: React.ClipboardEvent) => {
    e.preventDefault();
  };

  return (
    <div className="relative">
      <input
        type={visible ? "text" : "password"}
        {...field}
        placeholder={placeholder}
        autoComplete="new-password"
        className={`${className} pr-12`}
        onCopy={handleCopy}
      />
      <button
        type="button"
        onClick={() => setVisible((prev) => !prev)}
        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700 transition-colors duration-200"
        aria-label={visible ? "Hide password" : "Show password"}
      >
        {visible ? (
          <EyeOff className="w-4 h-4" />
        ) : (
          <Eye className="w-4 h-4" />
        )}
      </button>
    </div>
  );
};

export default CredentialPasswordField;
