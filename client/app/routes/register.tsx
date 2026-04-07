import React, { useState, useEffect } from "react";
import { Formik } from "formik";
import type { FormikHelpers } from "formik";
import { Link, Navigate, useLocation, useNavigate } from "react-router";
import { useAuth } from "~/stores/auth";
import PublicOnlyGuard from "~/components/PublicOnlyGuard";

interface RegisterFormValues {
  fullName: string;
  email: string;
  password: string;
  confirmPassword: string;
}

const Register = () => {
  const { signUp, signOut, isAuthenticated, isLoading, error, clearError } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [status, setStatus] = useState<{ registerError?: string } | null>(null);

  // Get the redirect path from location state
  const from = location.state?.from || "/";

  // Clear any existing errors when component mounts
  useEffect(() => {
    return () => {
      clearError();
      setStatus(null);
    };
  }, [clearError]);

  const handleSubmit = async (
    values: RegisterFormValues,
    { setSubmitting, setStatus }: FormikHelpers<RegisterFormValues>
  ) => {
    try {
      await signUp({
        user: {
          email: values.email,
          name: values.fullName,
          credential: values.password,
        },
      });
      // We are immediately logging out of the system to prevent Auth Guard's automatic redirection.
      await signOut();
      setStatus(null);
      // Navigate to sign in page upon successful registration      navigate("/signin", { state: { message: "Registration successful. Please sign in." } });
    } catch (err: any) {
      console.error("Sign up failed:", err);
      
      // Backend'den gelen hata mesajını parse et
      let errorMessage = "Sign up failed. Please try again.";
      
      if (err?.response?.data?.detail) {
        const detail = err.response.data.detail;
        
        // Pydantic validation hatalarını handle et
        if (Array.isArray(detail)) {
          errorMessage = detail.map((e: any) => e.msg || e.message).join(", ");
        } else if (typeof detail === 'string') {
          errorMessage = detail;
        }
        
        // Özel hata mesajları
        if (detail === "User already exists") {
          errorMessage = "An account with this email already exists. Please sign in.";
        }
      } else if (err?.response?.data?.message) {
        errorMessage = err.response.data.message;
      } else if (err?.message) {
        errorMessage = err.message;
      }
      
      // HTTP status code'a göre özel mesajlar
      if (err?.response?.status === 400) {
        // Validation error - mesajı olduğu gibi göster
      } else if (err?.response?.status >= 500) {
        errorMessage = "Server error. Please try again later.";
      }
      
      setStatus({ registerError: errorMessage });
    } finally {
      setSubmitting(false);
    }
  };

  // Redirect if already authenticated
  if (isAuthenticated) {
    return <Navigate to={from} replace />;
  }

  return (
    <PublicOnlyGuard>
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          {/* Header */}
          <div className="text-center mb-10">
            <h1 className="text-3xl font-semibold font-inter text-gray-900 text-start">
              Register
            </h1>
            {from !== "/" && (
              <p className="text-sm text-gray-600 mt-2">
                Please create an account to continue to your requested page
              </p>
            )}
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-md">
              <p className="text-red-600 text-sm">{error}</p>
            </div>
          )}

          <Formik
            initialValues={{
              fullName: "",
              email: "",
              password: "",
              confirmPassword: "",
            }}
            initialStatus={{}}
            validate={(values: RegisterFormValues) => {
              const errors: { [key: string]: string } = {};

              if (!values.fullName) {
                errors.fullName = "Required";
              } else if (values.fullName.length < 2) {
                errors.fullName = "Full name must be at least 2 characters";
              }

              if (!values.email) {
                errors.email = "Required";
              } else if (
                !/^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i.test(values.email)
              ) {
                errors.email = "Invalid email address";
              }

              if (!values.password) {
                errors.password = "Required";
              } else if (values.password.length < 6) {
                errors.password = "Password must be at least 6 characters";
              }

              if (!values.confirmPassword) {
                errors.confirmPassword = "Required";
              } else if (values.confirmPassword !== values.password) {
                errors.confirmPassword = "Passwords do not match";
              }

              return errors;
            }}
            onSubmit={handleSubmit}
            validateOnBlur
            validateOnChange
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
              values: RegisterFormValues;
              errors: any;
              touched: any;
              handleChange: any;
              handleBlur: any;
              handleSubmit: any;
              isSubmitting: boolean;
              status?: { registerError?: string };
            }) => (
              <form onSubmit={handleSubmit} className="space-y-6">
                {/* Full Name Field */}
                <div className="space-y-2">
                  <label className="block text-sm font-medium text-gray-700">
                    Full Name
                  </label>
                  <input
                    type="text"
                    name="fullName"
                    onChange={handleChange}
                    onBlur={handleBlur}
                    value={values.fullName}
                    disabled={isLoading || isSubmitting}
                    className={`w-full px-4 py-3 border rounded-md text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all duration-200 disabled:bg-gray-100 disabled:cursor-not-allowed ${errors.fullName && touched.fullName
                      ? "border-red-300 bg-red-50"
                      : "border-gray-300 bg-white hover:border-gray-400"
                      }`}
                    placeholder="John Doe"
                  />
                  {errors.fullName && touched.fullName && (
                    <p className="text-red-500 text-sm">{errors.fullName}</p>
                  )}
                </div>

                {/* Email Field */}
                <div className="space-y-2">
                  <label className="block text-sm font-medium text-gray-700">
                    Email
                  </label>
                  <input
                    type="email"
                    name="email"
                    onChange={handleChange}
                    onBlur={handleBlur}
                    value={values.email}
                    disabled={isLoading || isSubmitting}
                    className={`w-full px-4 py-3 border rounded-md text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all duration-200 disabled:bg-gray-100 disabled:cursor-not-allowed ${errors.email && touched.email
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
                  <label className="block text-sm font-medium text-gray-700">
                    Password
                  </label>
                  <input
                    type="password"
                    name="password"
                    onChange={handleChange}
                    onBlur={handleBlur}
                    value={values.password}
                    disabled={isLoading || isSubmitting}
                    className={`w-full px-4 py-3 border rounded-md text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all duration-200 disabled:bg-gray-100 disabled:cursor-not-allowed ${errors.password && touched.password
                      ? "border-red-300 bg-red-50"
                      : "border-gray-300 bg-white hover:border-gray-400"
                      }`}
                    placeholder="••••••"
                  />
                  {errors.password && touched.password && (
                    <p className="text-red-500 text-sm">{errors.password}</p>
                  )}
                </div>

                {/* Confirm Password Field */}
                <div className="space-y-2">
                  <label className="block text-sm font-medium text-gray-700">
                    Confirm Password
                  </label>
                  <input
                    type="password"
                    name="confirmPassword"
                    onChange={handleChange}
                    onBlur={handleBlur}
                    value={values.confirmPassword}
                    disabled={isLoading || isSubmitting}
                    className={`w-full px-4 py-3 border rounded-md text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all duration-200 disabled:bg-gray-100 disabled:cursor-not-allowed ${errors.confirmPassword && touched.confirmPassword
                      ? "border-red-300 bg-red-50"
                      : "border-gray-300 bg-white hover:border-gray-400"
                      }`}
                    placeholder="••••••"
                  />
                  {errors.confirmPassword && touched.confirmPassword && (
                    <p className="text-red-500 text-sm">
                      {errors.confirmPassword}
                    </p>
                  )}
                </div>

                {/* Register Button */}
                <button
                  type="submit"
                  disabled={isSubmitting || isLoading}
                  className={`w-full py-3 px-4 rounded-md font-medium text-white transition-all duration-200 ${isSubmitting || isLoading
                    ? "bg-purple-400 cursor-not-allowed"
                    : "bg-purple-600 hover:bg-purple-700 active:bg-purple-800"
                    }`}
                >
                  {isSubmitting || isLoading ? (
                    <div className="flex items-center justify-center">
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2"></div>
                      Creating account...
                    </div>
                  ) : (
                    "Create Account"
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
                  <button className="w-full py-3 px-4 border border-gray-300 rounded-md bg-white text-gray-700 font-medium hover:bg-gray-50 hover:border-gray-400 transition-all duration-200 flex items-center justify-center">
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
                    Sign Up With Google
                  </button>

                  <button className="w-full py-3 px-4 border border-gray-300 rounded-md bg-white text-gray-700 font-medium hover:bg-gray-50 hover:border-gray-400 transition-all duration-200 flex items-center justify-center">
                    <svg
                      className="w-5 h-5 mr-2"
                      fill="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
                    </svg>
                    Sign Up With Github
                  </button>
                </div>

                {/* Sign In Link */}
                <div className="text-center mt-8">
                  <p className="text-sm text-gray-600">
                    Already have an account?{" "}
                    <Link
                      to="/signin"
                      className="text-purple-600 hover:text-purple-700 font-medium transition-colors duration-200"
                    >
                      Sign In
                    </Link>
                  </p>
                </div>
              </form>
            )}
          </Formik>
        </div>
      </div>
    </PublicOnlyGuard>
  );
};

export default Register;
