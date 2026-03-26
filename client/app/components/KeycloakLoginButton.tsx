import React from "react";
import { useAuth } from "react-oidc-context";

interface KeycloakLoginButtonProps {
  disabled?: boolean;
}

export const KeycloakLoginButton: React.FC<KeycloakLoginButtonProps> = ({ disabled }) => {
  const auth = useAuth();

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => void auth.signinRedirect()}
      className="w-full py-3 px-4 border border-gray-300 rounded-md bg-white text-gray-700 font-medium hover:bg-gray-50 hover:border-gray-400 transition-all duration-200 flex items-center justify-center disabled:bg-gray-100 disabled:cursor-not-allowed"
    >
      <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2ZM13 17H11V15H13V17ZM13 13H11V7H13V13Z" fill="currentColor" />
      </svg>
      Sign In With Keycloak
    </button>
  );
};

