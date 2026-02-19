import { apiClient } from '../lib/api-client';
import { API_ENDPOINTS } from '../lib/config';

export interface TutorialProgressData {
    tutorial_id: string;
    current_step: number;
    completed_steps: string[];
}

export const getTutorialProgressList = async (): Promise<TutorialProgressData[]> => {
    return apiClient.get<TutorialProgressData[]>(API_ENDPOINTS.TUTORIAL_PROGRESS.LIST);
};

export const getTutorialProgress = async (tutorialId: string): Promise<TutorialProgressData> => {
    return apiClient.get<TutorialProgressData>(API_ENDPOINTS.TUTORIAL_PROGRESS.GET(tutorialId));
};

export const saveTutorialProgress = async (
    tutorialId: string,
    currentStep: number,
    completedSteps: string[]
): Promise<TutorialProgressData> => {
    return apiClient.put<TutorialProgressData>(API_ENDPOINTS.TUTORIAL_PROGRESS.SAVE(tutorialId), {
        current_step: currentStep,
        completed_steps: completedSteps,
    });
};

export const deleteTutorialProgress = async (tutorialId: string): Promise<void> => {
    return apiClient.delete(API_ENDPOINTS.TUTORIAL_PROGRESS.DELETE(tutorialId));
};
