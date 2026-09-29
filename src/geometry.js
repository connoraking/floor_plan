export const UNIT_TO_INCHES = Object.freeze({
  in: 1,
  ft: 12,
  cm: 1 / 2.54,
  m: 100 / 2.54,
});

export function toInches(value, unit) {
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) {
    throw new Error("Length must be greater than zero.");
  }
  if (!UNIT_TO_INCHES[unit]) throw new Error("Unsupported measurement unit.");
  return number * UNIT_TO_INCHES[unit];
}

export function distance(a, b) {
  return Math.hypot(b.x - a.x, b.y - a.y);
}

export function scaleFromCalibration(start, end, realLength, unit) {
  const drawnPoints = distance(start, end);
  if (!Number.isFinite(drawnPoints) || drawnPoints < 2) {
    throw new Error("The calibration points are too close together.");
  }
  return drawnPoints / toInches(realLength, unit);
}

export function normalizeAngle(value) {
  const number = Number(value) || 0;
  return ((number % 360) + 360) % 360;
}

export function furniturePath(item, pointsPerInch) {
  const width = item.width * pointsPerInch;
  const depth = item.depth * pointsPerInch;
  const left = -width / 2;
  const top = -depth / 2;

  if (item.type !== "l") {
    return `M ${left} ${top} H ${left + width} V ${top + depth} H ${left} Z`;
  }

  const armDepth = Math.min(item.armDepth, item.depth) * pointsPerInch;
  const returnWidth = Math.min(item.returnWidth, item.width) * pointsPerInch;
  return [
    `M ${left} ${top}`,
    `H ${left + width}`,
    `V ${top + armDepth}`,
    `H ${left + returnWidth}`,
    `V ${top + depth}`,
    `H ${left}`,
    "Z",
  ].join(" ");
}

export function resizeFurnitureFromHandle(item, deltaX, deltaY, axis, pointsPerInch) {
  if (!(pointsPerInch > 0)) throw new Error("A calibrated page scale is required to resize furniture.");

  const angle = normalizeAngle(item.rotation) * Math.PI / 180;
  const cosine = Math.cos(angle);
  const sine = Math.sin(angle);
  const localDeltaX = deltaX * cosine + deltaY * sine;
  const localDeltaY = -deltaX * sine + deltaY * cosine;
  const minimumWidth = item.type === "l" ? Number(item.returnWidth) + 0.25 : 1;
  const minimumDepth = item.type === "l" ? Number(item.armDepth) + 0.25 : 1;
  const snap = (value) => Math.round(value * 4) / 4;
  const width = axis === "width" || axis === "both"
    ? Math.max(minimumWidth, snap(Number(item.width) + localDeltaX / pointsPerInch))
    : Number(item.width);
  const depth = axis === "depth" || axis === "both"
    ? Math.max(minimumDepth, snap(Number(item.depth) + localDeltaY / pointsPerInch))
    : Number(item.depth);

  // Keep the opposite edge fixed, just like a conventional resize handle.
  const centerShiftX = (width - Number(item.width)) * pointsPerInch / 2;
  const centerShiftY = (depth - Number(item.depth)) * pointsPerInch / 2;
  return {
    width,
    depth,
    x: Number(item.x) + centerShiftX * cosine - centerShiftY * sine,
    y: Number(item.y) + centerShiftX * sine + centerShiftY * cosine,
  };
}

export function validateFurniture(input) {
  const item = {
    ...input,
    width: Number(input.width),
    depth: Number(input.depth),
    armDepth: Number(input.armDepth),
    returnWidth: Number(input.returnWidth),
  };
  if (!item.name?.trim()) throw new Error("Give this piece a name.");
  if (!(item.width > 0) || !(item.depth > 0)) {
    throw new Error("Width and depth must be greater than zero.");
  }
  if (item.type === "l") {
    if (!(item.armDepth > 0) || item.armDepth >= item.depth) {
      throw new Error("Arm depth must be smaller than the overall depth.");
    }
    if (!(item.returnWidth > 0) || item.returnWidth >= item.width) {
      throw new Error("Return width must be smaller than the overall width.");
    }
  }
  return item;
}

export function pointFromPointer(event, svg, page) {
  const bounds = svg.getBoundingClientRect();
  return {
    x: ((event.clientX - bounds.left) / bounds.width) * page.width,
    y: ((event.clientY - bounds.top) / bounds.height) * page.height,
  };
}

export function clamp(value, minimum, maximum) {
  return Math.min(maximum, Math.max(minimum, value));
}
