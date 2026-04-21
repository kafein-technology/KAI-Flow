import React, { useState, useEffect } from "react";
import type { FormikHelpers } from "formik";
import { ErrorMessage, Formik } from "formik";
import { Link, useNavigate } from "react-router";
import { useAuth } from "~/stores/auth";
import { KeycloakLoginButton } from "~/components/KeycloakLoginButton";
import PublicOnlyGuard from "~/components/PublicOnlyGuard";
import { config } from "~/lib/config";

interface SignInFormValues {
  email: string;
  password: string;
}

const Signin = () => {
  const navigate = useNavigate();
  const { signIn, isLoading, error, clearError } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const [status, setStatus] = useState<{ loginError?: string } | null>(null);
  const isKeycloakEnabled = !!window.VITE_KEYCLOAK_URL && !!window.VITE_KEYCLOAK_CLIENT_ID;

  useEffect(() => {
    return () => {
      clearError();
      setStatus(null);
    };
  }, [clearError]);

  const handleSubmit = async (
    values: SignInFormValues,
    { setSubmitting, setStatus }: FormikHelpers<SignInFormValues>
  ) => {
    try {
      // Önceki hataları temizle
      clearError();
      setStatus(null);
      await signIn(values);
      // Başarılı giriş sonrası yönlendirme
      navigate("/");
    } catch (err: any) {
      console.error("Sign in failed:", err);

      // Hata mesajını Formik status'una ayarla
      const errorMessage =
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        "Sign in failed. Please check your credentials.";
      setStatus({ loginError: errorMessage });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <PublicOnlyGuard>
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          {/* Header */}
          <div className="text-center mb-10">
            <h1 className="text-3xl font-semibold font-inter text-gray-900 text-start">
              Sign In
            </h1>
          </div>

          {/* Error Message */}
          {(error || status?.loginError) && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-md">
              <p className="text-red-600 text-sm">
                {status?.loginError || error}
              </p>
            </div>
          )}

          <Formik
            initialValues={{ email: "", password: "" }}
            initialStatus={{}}
            validate={(values: SignInFormValues) => {
              const errors: { [key: string]: string } = {};
              if (!values.email) {
                errors.email = "Email is required";
              } else if (
                !/^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i.test(values.email)
              ) {
                errors.email = "Invalid email address";
              }
              if (!values.password) {
                errors.password = "Password is required";
              } else if (values.password.length < 6) {
                errors.password = "Password must be at least 6 characters";
              }
              return errors;
            }}
            onSubmit={handleSubmit}
          >
            {({
              values,
              errors,
              touched,
              handleChange,
              handleBlur,
              handleSubmit,
              isSubmitting,
              status,
            }: {
              values: SignInFormValues;
              errors: any;
              touched: any;
              handleChange: any;
              handleBlur: any;
              handleSubmit: any;
              isSubmitting: boolean;
              status?: { loginError?: string };
            }) => (
              <form onSubmit={handleSubmit} className="space-y-6">
                {/* Email Field */}
                <div className="space-y-2">
                  <label className="block text-sm font-medium text-gray-700">
                    Email
                  </label>
                  <input
                    type="email"
                    name="email"
                    onChange={(e) => {
                      handleChange(e);
                      // Email değiştiğinde hataları temizle
                      if (status?.loginError || error) {
                        clearError();
                        setStatus(null);
                      }
                    }}
                    onBlur={handleBlur}
                    value={values.email}
                    disabled={isLoading || isSubmitting}
                    className={`w-full px-4 py-3 border rounded-md text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all duration-200 disabled:bg-gray-100 disabled:cursor-not-allowed ${
                      errors.email && touched.email
                        ? "border-red-300 bg-red-50"
                        : "border-gray-300 bg-white hover:border-gray-400"
                    }`}
                    placeholder="user@company.com"
                  />
                  {errors.email && touched.email && (
                    <p className="text-red-500 text-sm">{errors.email}</p>
                  )}
                </div>

                {/* Password Field */}
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <label className="block text-sm font-medium text-gray-700">
                      Password
                    </label>
                  </div>
                  <div className="relative">
                    <input
                      type={showPassword ? "text" : "password"}
                      name="password"
                      onChange={(e) => {
                        handleChange(e);
                        // Şifre değiştiğinde hataları temizle
                        if (status?.loginError || error) {
                          clearError();
                          setStatus(null);
                        }
                      }}
                      onBlur={handleBlur}
                      value={values.password}
                      disabled={isLoading || isSubmitting}
                      className={`w-full px-4 py-3 border rounded-md text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all duration-200 disabled:bg-gray-100 disabled:cursor-not-allowed ${
                        errors.password && touched.password
                          ? "border-red-300 bg-red-50"
                          : "border-gray-300 bg-white hover:border-gray-400"
                      }`}
                      placeholder="••••••"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 transform -translate-y-1/2 text-sm text-purple-600 hover:text-purple-700 transition-colors duration-200"
                    >
                      {showPassword ? "Hide" : "Show"}
                    </button>
                  </div>

                  {errors.password && touched.password && (
                    <p className="text-red-500 text-sm">{errors.password}</p>
                  )}
                </div>

                {/* Login Button */}
                <button
                  type="submit"
                  disabled={isSubmitting || isLoading}
                  className={`w-full py-3 px-4 rounded-md font-medium text-white transition-all duration-200 ${
                    isSubmitting || isLoading
                      ? "bg-purple-400 cursor-not-allowed"
                      : "bg-purple-600 hover:bg-purple-700 active:bg-purple-800"
                  }`}
                >
                  {isSubmitting || isLoading ? (
                    <div className="flex items-center justify-center">
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2"></div>
                      Signing in...
                    </div>
                  ) : (
                    "Sign In"
                  )}
                </button>

                {/* Divider */}
                <div className="relative my-6">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-gray-300"></div>
                  </div>
                  <div className="relative flex justify-center text-sm">
                    <span className="px-2 bg-gray-50 text-gray-500">OR</span>
                  </div>
                </div>

                {/* Social Login Buttons */}
                <div className="space-y-3">
                  {isKeycloakEnabled && (
                    <KeycloakLoginButton disabled={isLoading || isSubmitting} />
                  )}

                  <button
                    type="button"
                    disabled={isLoading || isSubmitting}
                    className="w-full py-3 px-4 border border-gray-300 rounded-md bg-white text-gray-700 font-medium hover:bg-gray-50 hover:border-gray-400 transition-all duration-200 flex items-center justify-center disabled:bg-gray-100 disabled:cursor-not-allowed"
                  >
                    <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24">
                      <path
                        fill="#4285f4"
                        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                      />
                      <path
                        fill="#34a853"
                        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                      />
                      <path
                        fill="#fbbc05"
                        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                      />
                      <path
                        fill="#ea4335"
                        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                      />
                    </svg>
                    Sign In With Google
                  </button>

                  <button
                    type="button"
                    disabled={isLoading || isSubmitting}
                    className="w-full py-3 px-4 border border-gray-300 rounded-md bg-white text-gray-700 font-medium hover:bg-gray-50 hover:border-gray-400 transition-all duration-200 flex items-center justify-center disabled:bg-gray-100 disabled:cursor-not-allowed"
                  >
                    <svg
                      className="w-5 h-5 mr-2"
                      fill="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
                    </svg>
                    Sign In With Github
                  </button>
                </div>

                {/* Sign Up Link */}
                {!config.IS_ENTERPRISE && (
                  <div className="text-center mt-8">
                    <p className="text-sm text-gray-600">
                      Don't have an account?{" "}
                      <Link
                        to="/register"
                        className="text-purple-600 hover:text-purple-700 font-medium transition-colors duration-200"
                      >
                        Sign Up
                      </Link>
                    </p>
                  </div>
                )}
              </form>
            )}
          </Formik>
        </div>
      </div>
    </PublicOnlyGuard>
  );
};

export default Signin;
