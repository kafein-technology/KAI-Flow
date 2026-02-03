export { };

declare module '*.svg?react' {
    import React from 'react';
    const ReactComponent: React.FC<React.SVGProps<SVGSVGElement>>;
    export default ReactComponent;
}

declare global {
    interface Window {
        VITE_BASE_PATH: string;
        VITE_API_BASE_URL: string;
        VITE_KEYCLOAK_URL: string;
        VITE_KEYCLOAK_REALM: string;
        VITE_KEYCLOAK_CLIENT_ID: string;
        VITE_API_VERSION: string;
        VITE_APP_NAME: string;
        VITE_NODE_ENV: string;
        VITE_ENABLE_LOGGING: string;
    }
}
