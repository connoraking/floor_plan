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
