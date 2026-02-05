import React, { useState, useEffect } from "react";
import { User, Save, X } from "~/icons/index";
import DashboardSidebar from "~/components/dashboard/DashboardSidebar";
import { useAuth } from "~/stores/auth";
import { useSnackbar } from "notistack";
import Loading from "~/components/Loading";
import AuthGuard from "~/components/AuthGuard";

interface UserProfileForm {
  first_name: string;
  last_name: string;
  email: string;
}

function SettingsLayout() {
  const { user, updateProfile, isLoading: loading } = useAuth();
  const { enqueueSnackbar } = useSnackbar();
  const [formData, setFormData] = useState<UserProfileForm>({
    first_name: "",
    last_name: "",
    email: "",
  });
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Initialize form data when user data is loaded
  useEffect(() => {
    if (user) {
      const nameParts = user.full_name?.split(" ") || ["", ""];
      setFormData({
        first_name: nameParts[0] || "",
        last_name: nameParts.slice(1).join(" ") || "",
        email: user.email || "",
      });
    }
  }, [user]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSave = async () => {
    if (!formData.first_name.trim() || !formData.last_name.trim()) {
      enqueueSnackbar("First name and last name are required", {
        variant: "error",
      });
      return;
    }

    setIsSaving(true);
    try {
      await updateProfile({
        full_name: `${formData.first_name.trim()} ${formData.last_name.trim()}`,
      });

      enqueueSnackbar("Profile updated successfully", { variant: "success" });
      setIsEditing(false);
    } catch (error: any) {
      enqueueSnackbar(error.message || "Failed to update profile", {
        variant: "error",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    if (user) {
      const nameParts = user.full_name?.split(" ") || ["", ""];
      setFormData({
        first_name: nameParts[0] || "",
        last_name: nameParts.slice(1).join(" ") || "",
        email: user.email || "",
      });
    }
    setIsEditing(false);
  };

  if (loading) {
    return (
      <div className="flex h-screen bg-background text-foreground">
        <DashboardSidebar />
        <main className="flex-1 overflow-hidden flex items-center justify-center">
          <Loading size="sm" />
        </main>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-background text-foreground">
      <DashboardSidebar />
      <main className="flex-1 overflow-hidden">
        <div className="h-full overflow-y-auto p-6">
          <div className="max-w-2xl mx-auto">
            {/* Header Section */}
            <div className="mb-8">
              <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-600 to-blue-600 bg-clip-text text-transparent">
                Settings
              </h1>
              <p className="text-gray-600 text-lg mt-2">
                Manage your account settings and preferences.
              </p>
            </div>

            {/* Profile Settings Card */}
            <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center shadow-lg">
                    <User className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <h2 className="text-xl font-semibold text-gray-900">
                      Basic Information
                    </h2>
                    <p className="text-sm text-gray-600">
                      Update your personal information
                    </p>
                  </div>
                </div>

                {!isEditing && (
                  <button
                    onClick={() => setIsEditing(true)}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors duration-200"
                  >
                    Edit Profile
                  </button>
                )}
              </div>

              <div className="space-y-4">
                {/* First Name */}
                <div>
                  <label
                    htmlFor="first_name"
                    className="block text-sm font-medium text-gray-700 mb-1"
                  >
                    First Name *
                  </label>
                  <input
                    type="text"
                    id="first_name"
                    name="first_name"
                    value={formData.first_name}
                    onChange={handleInputChange}
                    disabled={!isEditing}
                    className={`w-full px-4 py-3 border rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 ${isEditing
                        ? "bg-white border-gray-300"
                        : "bg-gray-50 border-gray-200 text-gray-600"
                      }`}
                    placeholder="Enter your first name"
                  />
                </div>

                {/* Last Name */}
                <div>
                  <label
                    htmlFor="last_name"
                    className="block text-sm font-medium text-gray-700 mb-1"
                  >
                    Last Name *
                  </label>
                  <input
                    type="text"
                    id="last_name"
                    name="last_name"
                    value={formData.last_name}
                    onChange={handleInputChange}
                    disabled={!isEditing}
                    className={`w-full px-4 py-3 border rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 ${isEditing
                        ? "bg-white border-gray-300"
                        : "bg-gray-50 border-gray-200 text-gray-600"
                      }`}
                    placeholder="Enter your last name"
                  />
                </div>

                {/* Email */}
                <div>
                  <label
                    htmlFor="email"
                    className="block text-sm font-medium text-gray-700 mb-1"
                  >
                    Email
                  </label>
                  <input
                    type="email"
                    id="email"
                    name="email"
                    value={formData.email}
                    disabled={true}
                    className="w-full px-4 py-3 border bg-gray-50 border-gray-200 text-gray-600 rounded-xl cursor-not-allowed"
                    placeholder="Enter your email address"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Email cannot be changed. Contact support if you need to
                    update your email.
                  </p>
                </div>

                {/* Action Buttons - Only show when editing */}
                {isEditing && (
                  <div className="flex items-center gap-3 pt-4 border-t border-gray-200">
                    <button
                      onClick={handleSave}
                      disabled={isSaving}
                      className="flex items-center gap-2 px-6 py-3 bg-green-600 text-white rounded-xl hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-200"
                    >
                      {isSaving ? (
                        <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      ) : (
                        <Save className="w-4 h-4" />
                      )}
                      {isSaving ? "Saving..." : "Save Changes"}
                    </button>

                    <button
                      onClick={handleCancel}
                      disabled={isSaving}
                      className="flex items-center gap-2 px-6 py-3 bg-gray-500 text-white rounded-xl hover:bg-gray-600 disabled:opacity-50 transition-colors duration-200"
                    >
                      <X className="w-4 h-4" />
                      Cancel
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Additional Settings Cards can be added here in the future */}
          </div>
        </div>
      </main>
    </div>
  );
}

export default function ProtectedSettingsLayout() {
  return (
    <AuthGuard>
      <SettingsLayout />
    </AuthGuard>
  );
}
