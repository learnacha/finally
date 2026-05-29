import type { Config } from "jest";

const config: Config = {
  testEnvironment: "jsdom",
  preset: "ts-jest",
  testMatch: [
    "**/__tests__/**/*.test.{ts,tsx}",
    "**/__tests__/**/*.spec.{ts,tsx}",
  ],
  setupFilesAfterEnv: ["<rootDir>/jest.setup.ts"],
  moduleNameMapper: {
    "\\.(css|scss)$": "<rootDir>/__mocks__/styleMock.ts",
    "\\.(png|jpg|svg|gif)$": "<rootDir>/__mocks__/fileMock.ts",
    "next/font/(.*)": "<rootDir>/__mocks__/nextFontMock.ts",
  },
  transform: {
    "^.+\\.(ts|tsx)$": [
      "ts-jest",
      {
        tsconfig: {
          jsx: "react-jsx",
        },
      },
    ],
  },
};

export default config;
