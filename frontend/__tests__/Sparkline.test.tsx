/**
 * Tests for the Sparkline canvas component.
 *
 * Note: Canvas rendering is not fully testable in jsdom, but we can verify
 * the component renders without errors, passes through props, and handles
 * edge cases (empty data, single data point).
 */

import React from "react";
import { render } from "@testing-library/react";
import { Sparkline } from "../components/Sparkline";

// Mock canvas context since jsdom doesn't implement it
const mockContext = {
  clearRect: jest.fn(),
  beginPath: jest.fn(),
  moveTo: jest.fn(),
  lineTo: jest.fn(),
  stroke: jest.fn(),
  fill: jest.fn(),
  closePath: jest.fn(),
  createLinearGradient: jest.fn(() => ({
    addColorStop: jest.fn(),
  })),
  scale: jest.fn(),
  strokeStyle: "",
  fillStyle: "",
  lineWidth: 0,
  lineJoin: "",
};

beforeAll(() => {
  // jsdom doesn't implement getContext; stub it out
  HTMLCanvasElement.prototype.getContext = jest.fn(() => mockContext as unknown as CanvasRenderingContext2D);
});

afterEach(() => {
  jest.clearAllMocks();
});

const sampleData = [
  { time: 1000, price: 190.0 },
  { time: 1500, price: 191.0 },
  { time: 2000, price: 192.5 },
  { time: 2500, price: 191.8 },
  { time: 3000, price: 193.0 },
];

describe("Sparkline", () => {
  it("renders a canvas element", () => {
    const { container } = render(<Sparkline data={sampleData} />);
    const canvas = container.querySelector("canvas");
    expect(canvas).toBeInTheDocument();
  });

  it("renders without crashing with empty data", () => {
    expect(() => render(<Sparkline data={[]} />)).not.toThrow();
  });

  it("renders without crashing with a single data point", () => {
    expect(() =>
      render(<Sparkline data={[{ time: 1000, price: 190.0 }]} />)
    ).not.toThrow();
  });

  it("accepts custom width and height props", () => {
    const { container } = render(
      <Sparkline data={sampleData} width={120} height={40} />
    );
    const canvas = container.querySelector("canvas");
    expect(canvas).toBeInTheDocument();
  });

  it("accepts positive=true prop without crashing", () => {
    expect(() =>
      render(<Sparkline data={sampleData} positive={true} />)
    ).not.toThrow();
  });

  it("accepts positive=false prop without crashing", () => {
    expect(() =>
      render(<Sparkline data={sampleData} positive={false} />)
    ).not.toThrow();
  });

  it("calls getContext with '2d'", () => {
    render(<Sparkline data={sampleData} />);
    expect(HTMLCanvasElement.prototype.getContext).toHaveBeenCalledWith("2d");
  });
});
