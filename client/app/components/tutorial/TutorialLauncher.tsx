import React, { useState } from "react";
import { BookOpen, Play, Star, Clock, Tag } from "lucide-react";
import {
  TUTORIAL_WORKFLOWS,
  type TutorialWorkflow,
} from "../../data/tutorialWorkflows";

interface TutorialLauncherProps {
  onLaunchTutorial: (tutorialId: string) => void;
}

export default function TutorialLauncher({
  onLaunchTutorial,
}: TutorialLauncherProps) {
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [selectedDifficulty, setSelectedDifficulty] = useState<string>("all");

  const categories = [
    "all",
    ...Array.from(new Set(TUTORIAL_WORKFLOWS.map((t) => t.category))),
  ];
  const difficulties = ["all", "Beginner", "Intermediate", "Advanced"];

  const filteredTutorials = TUTORIAL_WORKFLOWS.filter((tutorial) => {
    const categoryMatch =
      selectedCategory === "all" || tutorial.category === selectedCategory;
    const difficultyMatch =
      selectedDifficulty === "all" ||
      tutorial.difficulty === selectedDifficulty;
    return categoryMatch && difficultyMatch;
  });

  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty) {
      case "Beginner":
        return "bg-green-100 text-green-800";
      case "Intermediate":
        return "bg-yellow-100 text-yellow-800";
      case "Advanced":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case "AI & Chatbots":
        return "🤖";
      case "Document Processing":
        return "📄";
      case "Automation":
        return "";
      default:
        return "";
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-lg p-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <BookOpen className="w-8 h-8 text-blue-600" />
        <div>
          <h2 className="text-2xl font-bold text-gray-900">
            Tutorial Workflows
          </h2>
          <p className="text-gray-600">
            Step-by-step guides to build amazing AI workflows
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-4 mb-6">
        <div className="flex-1">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Category
          </label>
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {categories.map((category) => (
              <option key={category} value={category}>
                {category === "all" ? "All Categories" : category}
              </option>
            ))}
          </select>
        </div>
        <div className="flex-1">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Difficulty
          </label>
          <select
            value={selectedDifficulty}
            onChange={(e) => setSelectedDifficulty(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {difficulties.map((difficulty) => (
              <option key={difficulty} value={difficulty}>
                {difficulty === "all" ? "All Difficulties" : difficulty}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Tutorial Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredTutorials.map((tutorial) => (
          <div
            key={tutorial.id}
            className="border border-gray-200 rounded-lg p-6 hover:shadow-md transition-all duration-200 hover:border-blue-300"
          >
            {/* Tutorial Header */}
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-2">
                <span className="text-2xl">
                  {getCategoryIcon(tutorial.category)}
                </span>
                <div>
                  <h3 className="font-semibold text-gray-900 text-lg">
                    {tutorial.name}
                  </h3>
                  <p className="text-sm text-gray-500">{tutorial.category}</p>
                </div>
              </div>
              <span
                className={`px-2 py-1 rounded-full text-xs font-medium ${getDifficultyColor(
                  tutorial.difficulty
                )}`}
              >
                {tutorial.difficulty}
              </span>
            </div>

            {/* Description */}
            <p className="text-gray-600 text-sm mb-4 line-clamp-3">
              {tutorial.description}
            </p>

            {/* Metadata */}
            <div className="flex items-center gap-4 mb-4 text-sm text-gray-500">
              <div className="flex items-center gap-1">
                <Clock className="w-4 h-4" />
                {tutorial.estimatedTime}
              </div>
              <div className="flex items-center gap-1">
                <Play className="w-4 h-4" />
                {tutorial.steps.length} steps
              </div>
            </div>

            {/* Prerequisites */}
            {tutorial.prerequisites.length > 0 && (
              <div className="mb-4">
                <p className="text-xs font-medium text-gray-700 mb-2">
                  Prerequisites:
                </p>
                <div className="flex flex-wrap gap-1">
                  {tutorial.prerequisites.map((prereq, index) => (
                    <span
                      key={index}
                      className="px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded-full"
                    >
                      {prereq}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Tags */}
            <div className="flex flex-wrap gap-1 mb-4">
              {tutorial.tags.slice(0, 3).map((tag, index) => (
                <span
                  key={index}
                  className="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded-full"
                >
                  {tag}
                </span>
              ))}
              {tutorial.tags.length > 3 && (
                <span className="px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded-full">
                  +{tutorial.tags.length - 3}
                </span>
              )}
            </div>

            {/* Launch Button */}
            <button
              onClick={() => onLaunchTutorial(tutorial.id)}
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 transition-colors duration-200 flex items-center justify-center gap-2"
            >
              <Play className="w-4 h-4" />
              Start Tutorial
            </button>
          </div>
        ))}
      </div>

      {/* Empty State */}
      {filteredTutorials.length === 0 && (
        <div className="text-center py-12">
          <BookOpen className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-600 mb-2">
            No tutorials found
          </h3>
          <p className="text-gray-500">
            Try adjusting your filters to see more tutorials.
          </p>
        </div>
      )}

      {/* Footer */}
      <div className="mt-8 pt-6 border-t border-gray-200 text-center">
        <p className="text-sm text-gray-500">
          Need help? Check out our{" "}
          <a href="#" className="text-blue-600 hover:text-blue-700 underline">
            documentation
          </a>{" "}
          or{" "}
          <a href="#" className="text-blue-600 hover:text-blue-700 underline">
            community forum
          </a>
          .
        </p>
      </div>
    </div>
  );
}
