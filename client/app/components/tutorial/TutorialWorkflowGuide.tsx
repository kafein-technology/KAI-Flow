import React, { useState, useEffect } from "react";
import {
  BookOpen,
  Play,
  CheckCircle,
  ChevronRight,
  ChevronLeft,
  X,
  Info,
  Lightbulb,
  Code,
  Zap,
} from "~/icons/index";
import {
  TUTORIAL_WORKFLOWS,
  type TutorialWorkflow,
  type TutorialStep,
} from "../../data/tutorialWorkflows";

interface TutorialWorkflowGuideProps {
  isOpen: boolean;
  onClose: () => void;
  selectedTutorial?: string;
}

export default function TutorialWorkflowGuide({
  isOpen,
  onClose,
  selectedTutorial,
}: TutorialWorkflowGuideProps) {
  const [currentTutorial, setCurrentTutorial] =
    useState<TutorialWorkflow | null>(null);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [completedSteps, setCompletedSteps] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (selectedTutorial) {
      const tutorial = TUTORIAL_WORKFLOWS.find(
        (t) => t.id === selectedTutorial
      );
      if (tutorial) {
        setCurrentTutorial(tutorial);
        setCurrentStepIndex(0);
        setCompletedSteps(new Set());
      }
    }
  }, [selectedTutorial]);

  useEffect(() => {
    if (isOpen && !currentTutorial) {
      setCurrentTutorial(TUTORIAL_WORKFLOWS[0]);
    }
  }, [isOpen, currentTutorial]);

  const handleStepComplete = (stepId: string) => {
    setCompletedSteps((prev) => new Set([...prev, stepId]));
  };

  const handleStepUncomplete = (stepId: string) => {
    setCompletedSteps((prev) => {
      const newSet = new Set(prev);
      newSet.delete(stepId);
      return newSet;
    });
  };

  const nextStep = () => {
    if (
      currentTutorial &&
      currentStepIndex < currentTutorial.steps.length - 1
    ) {
      setCurrentStepIndex(currentStepIndex + 1);
    }
  };

  const previousStep = () => {
    if (currentStepIndex > 0) {
      setCurrentStepIndex(currentStepIndex - 1);
    }
  };

  const selectTutorial = (tutorial: TutorialWorkflow) => {
    setCurrentTutorial(tutorial);
    setCurrentStepIndex(0);
    setCompletedSteps(new Set());
  };

  const getProgressPercentage = () => {
    if (!currentTutorial) return 0;
    return (completedSteps.size / currentTutorial.steps.length) * 100;
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-6xl h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div className="flex items-center gap-3">
            <BookOpen className="w-8 h-8 text-blue-600" />
            <div>
              <h2 className="text-2xl font-bold text-gray-900">
                Tutorial Workflow Guide
              </h2>
              <p className="text-gray-600">
                Step-by-step guides for building AI workflows
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 p-2 rounded-lg hover:bg-gray-100"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        <div className="flex-1 flex overflow-hidden">
          {/* Sidebar - Tutorial Selection */}
          <div className="w-80 border-r border-gray-200 bg-gray-50 overflow-y-auto">
            <div className="p-4">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                Available Tutorials
              </h3>
              <div className="space-y-3">
                {TUTORIAL_WORKFLOWS.map((tutorial) => (
                  <button
                    key={tutorial.id}
                    onClick={() => selectTutorial(tutorial)}
                    className={`w-full text-left p-4 rounded-lg border transition-all ${currentTutorial?.id === tutorial.id
                        ? "border-blue-500 bg-blue-50 shadow-md"
                        : "border-gray-200 bg-white hover:border-gray-300 hover:shadow-sm"
                      }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <h4 className="font-semibold text-gray-900">
                          {tutorial.name}
                        </h4>
                        <p className="text-sm text-gray-600 mt-1">
                          {tutorial.description}
                        </p>
                        <div className="flex items-center gap-2 mt-2">
                          <span
                            className={`px-2 py-1 rounded-full text-xs font-medium ${tutorial.difficulty === "Beginner"
                                ? "bg-green-100 text-green-800"
                                : tutorial.difficulty === "Intermediate"
                                  ? "bg-yellow-100 text-yellow-800"
                                  : "bg-red-100 text-red-800"
                              }`}
                          >
                            {tutorial.difficulty}
                          </span>
                          <span className="text-xs text-gray-500">
                            {tutorial.estimatedTime}
                          </span>
                        </div>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Main Content - Tutorial Steps */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {currentTutorial && (
              <>
                {/* Tutorial Header */}
                <div className="p-6 border-b border-gray-200">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-xl font-bold text-gray-900">
                        {currentTutorial.name}
                      </h3>
                      <p className="text-gray-600 mt-1">
                        {currentTutorial.description}
                      </p>
                      <div className="flex items-center gap-4 mt-3">
                        <span className="text-sm text-gray-500">
                          <Code className="w-4 h-4 inline mr-1" />
                          {currentTutorial.category}
                        </span>
                        <span className="text-sm text-gray-500">
                          <Zap className="w-4 h-4 inline mr-1" />
                          {currentTutorial.estimatedTime}
                        </span>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-bold text-blue-600">
                        {Math.round(getProgressPercentage())}%
                      </div>
                      <div className="text-sm text-gray-500">Complete</div>
                    </div>
                  </div>

                  {/* Progress Bar */}
                  <div className="mt-4">
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                        style={{ width: `${getProgressPercentage()}%` }}
                      ></div>
                    </div>
                  </div>
                </div>

                {/* Step Content */}
                <div className="flex-1 overflow-y-auto p-6">
                  {currentTutorial.steps[currentStepIndex] && (
                    <div className="max-w-4xl mx-auto">
                      {/* Step Header */}
                      <div className="mb-6">
                        <div className="flex items-center gap-3 mb-4">
                          <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                            <span className="text-blue-600 font-bold text-lg">
                              {currentStepIndex + 1}
                            </span>
                          </div>
                          <div>
                            <h4 className="text-xl font-bold text-gray-900">
                              {currentTutorial.steps[currentStepIndex].title}
                            </h4>
                            <p className="text-gray-600">
                              {
                                currentTutorial.steps[currentStepIndex]
                                  .description
                              }
                            </p>
                          </div>
                        </div>
                      </div>

                      {/* Step Instructions */}
                      <div className="bg-blue-50 rounded-lg p-6 mb-6">
                        <h5 className="font-semibold text-blue-900 mb-3 flex items-center gap-2">
                          <Play className="w-5 h-5" />
                          Step-by-Step Instructions
                        </h5>
                        <ol className="space-y-3">
                          {currentTutorial.steps[
                            currentStepIndex
                          ].instructions.map((instruction, index) => (
                            <li key={index} className="flex items-start gap-3">
                              <span className="w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0 mt-0.5">
                                {index + 1}
                              </span>
                              <span className="text-blue-900">
                                {instruction}
                              </span>
                            </li>
                          ))}
                        </ol>
                      </div>

                      {/* Tips */}
                      {currentTutorial.steps[currentStepIndex].tips.length >
                        0 && (
                          <div className="bg-yellow-50 rounded-lg p-6 mb-6">
                            <h5 className="font-semibold text-yellow-900 mb-3 flex items-center gap-2">
                              <Lightbulb className="w-5 h-5" />
                              Pro Tips
                            </h5>
                            <ul className="space-y-2">
                              {currentTutorial.steps[currentStepIndex].tips.map(
                                (tip, index) => (
                                  <li
                                    key={index}
                                    className="flex items-start gap-3"
                                  >
                                    <span className="w-2 h-2 bg-yellow-600 rounded-full mt-2 flex-shrink-0"></span>
                                    <span className="text-yellow-900">{tip}</span>
                                  </li>
                                )
                              )}
                            </ul>
                          </div>
                        )}

                      {/* Expected Outcome */}
                      <div className="bg-green-50 rounded-lg p-6 mb-6">
                        <h5 className="font-semibold text-green-900 mb-3 flex items-center gap-2">
                          <CheckCircle className="w-5 h-5" />
                          Expected Outcome
                        </h5>
                        <p className="text-green-900">
                          {
                            currentTutorial.steps[currentStepIndex]
                              .expectedOutcome
                          }
                        </p>
                      </div>

                      {/* Step Completion */}
                      <div className="flex items-center justify-between">
                        <button
                          onClick={() => {
                            const stepId =
                              currentTutorial.steps[currentStepIndex].id;
                            if (completedSteps.has(stepId)) {
                              handleStepUncomplete(stepId);
                            } else {
                              handleStepComplete(stepId);
                            }
                          }}
                          className={`px-6 py-3 rounded-lg font-medium transition-all ${completedSteps.has(
                            currentTutorial.steps[currentStepIndex].id
                          )
                              ? "bg-green-100 text-green-800 hover:bg-green-200"
                              : "bg-blue-600 text-white hover:bg-blue-700"
                            }`}
                        >
                          {completedSteps.has(
                            currentTutorial.steps[currentStepIndex].id
                          ) ? (
                            <>
                              <CheckCircle className="w-5 h-5 inline mr-2" />
                              Step Completed
                            </>
                          ) : (
                            <>
                              <CheckCircle className="w-5 h-5 inline mr-2" />
                              Mark as Complete
                            </>
                          )}
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                {/* Navigation Footer */}
                <div className="p-6 border-t border-gray-200 bg-gray-50">
                  <div className="flex items-center justify-between">
                    <button
                      onClick={previousStep}
                      disabled={currentStepIndex === 0}
                      className={`px-4 py-2 rounded-lg font-medium transition-all ${currentStepIndex === 0
                          ? "bg-gray-200 text-gray-400 cursor-not-allowed"
                          : "bg-white text-gray-700 hover:bg-gray-100 border border-gray-300"
                        }`}
                    >
                      <ChevronLeft className="w-5 h-5 inline mr-2" />
                      Previous
                    </button>

                    <div className="text-sm text-gray-500">
                      Step {currentStepIndex + 1} of{" "}
                      {currentTutorial.steps.length}
                    </div>

                    <button
                      onClick={nextStep}
                      disabled={
                        currentStepIndex === currentTutorial.steps.length - 1
                      }
                      className={`px-4 py-2 rounded-lg font-medium transition-all ${currentStepIndex === currentTutorial.steps.length - 1
                          ? "bg-gray-200 text-gray-400 cursor-not-allowed"
                          : "bg-blue-600 text-white hover:bg-blue-700"
                        }`}
                    >
                      Next
                      <ChevronRight className="w-5 h-5 inline ml-2" />
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
