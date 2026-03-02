import React, { useState } from "react";
import { BookOpen, X } from "lucide-react";
import TutorialLauncher from "./TutorialLauncher";
import TutorialWorkflowGuide from "./TutorialWorkflowGuide";
import { useTutorialProgress } from "../../stores/tutorialProgress";

export default function TutorialButton() {
  const [showLauncher, setShowLauncher] = useState(false);
  const [showGuide, setShowGuide] = useState(false);
  const [selectedTutorial, setSelectedTutorial] = useState<
    string | undefined
  >();
  const { hasAnyProgress } = useTutorialProgress();

  const handleTutorialButtonClick = () => {
    if (hasAnyProgress()) {
      setSelectedTutorial(undefined);
      setShowGuide(true);
    } else {
      setShowLauncher(true);
    }
  };

  const handleLaunchTutorial = (tutorialId: string) => {
    setSelectedTutorial(tutorialId);
    setShowLauncher(false);
    setShowGuide(true);
  };

  const handleCloseGuide = () => {
    setShowGuide(false);
    setSelectedTutorial(undefined);
  };

  return (
    <>
      {/* Tutorial Button */}
      <button
        onClick={handleTutorialButtonClick}
        className="fixed bottom-6 left-6 bg-blue-600 text-white p-4 rounded-full shadow-lg hover:bg-blue-700 transition-all duration-200 hover:scale-110 z-40"
        title="Open Tutorials"
      >
        <BookOpen className="w-6 h-6" />
      </button>

      {/* Tutorial Launcher Modal */}
      {showLauncher && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-7xl max-h-[90vh] overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b border-gray-200">
              <h2 className="text-2xl font-bold text-gray-900">
                Tutorial Workflows
              </h2>
              <button
                onClick={() => setShowLauncher(false)}
                className="text-gray-400 hover:text-gray-600 p-2 rounded-lg hover:bg-gray-100"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            {/* Content */}
            <div className="overflow-y-auto max-h-[calc(90vh-120px)]">
              <TutorialLauncher onLaunchTutorial={handleLaunchTutorial} />
            </div>
          </div>
        </div>
      )}

      {/* Tutorial Guide Modal */}
      {showGuide && (
        <TutorialWorkflowGuide
          isOpen={showGuide}
          onClose={handleCloseGuide}
          selectedTutorial={selectedTutorial}
        />
      )}
    </>
  );
}
