import { ApiError } from "./api";

export type AuthField = "email" | "password" | "name";

export type AuthFormFeedback = {
  title: string;
  message: string;
  fieldErrors: Partial<Record<AuthField, string>>;
  /** Hint shown below the alert (e.g. switch to login) */
  hint?: string;
};

type ValidationItem = { loc?: (string | number)[]; msg?: string; type?: string };

function fieldFromLoc(loc: (string | number)[] | undefined): AuthField | null {
  if (!loc) return null;
  const key = loc[loc.length - 1];
  if (key === "email" || key === "password" || key === "name") return key;
  return null;
}

function mapValidationMessage(field: AuthField, msg: string, type?: string): string {
  const lower = msg.toLowerCase();
  if (field === "email") {
    if (lower.includes("valid email") || type === "value_error") {
      return "Enter a valid email address (e.g. you@example.com).";
    }
    return "Please check your email address.";
  }
  if (field === "password") {
    if (type === "string_too_short" || lower.includes("at least 6")) {
      return "Password must be at least 6 characters.";
    }
    if (type === "string_too_long" || lower.includes("at most")) {
      return "Password is too long (maximum 128 characters).";
    }
    if (lower.includes("required") || lower.includes("missing")) {
      return "Password is required.";
    }
    return "Please choose a stronger password.";
  }
  if (field === "name") {
    if (type === "string_too_long") return "Name is too long (maximum 120 characters).";
    return "Please enter your name.";
  }
  return msg;
}

function parseValidationErrors(detail: unknown): Partial<Record<AuthField, string>> {
  if (!Array.isArray(detail)) return {};
  const errors: Partial<Record<AuthField, string>> = {};
  for (const item of detail as ValidationItem[]) {
    const field = fieldFromLoc(item.loc);
    if (!field || !item.msg) continue;
    if (!errors[field]) {
      errors[field] = mapValidationMessage(field, item.msg, item.type);
    }
  }
  return errors;
}

function detailString(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return (detail as ValidationItem[])
      .map((e) => e.msg)
      .filter(Boolean)
      .join(" ");
  }
  return "";
}

export function getAuthFormFeedback(err: unknown, mode: "login" | "register"): AuthFormFeedback {
  const empty: AuthFormFeedback = { title: "", message: "", fieldErrors: {} };

  if (err instanceof TypeError || (err instanceof Error && err.message === "Failed to fetch")) {
    return {
      title: "Connection problem",
      message: "We couldn't reach the server. Check your internet connection and try again.",
      fieldErrors: {},
      hint: "If you're running locally, make sure the API is started on port 8010.",
    };
  }

  if (!(err instanceof ApiError)) {
    return {
      title: mode === "login" ? "Sign in failed" : "Registration failed",
      message: err instanceof Error ? err.message : "Something went wrong. Please try again.",
      fieldErrors: {},
    };
  }

  const { status } = err;
  const raw = detailString(err.detail);
  const fieldErrors = parseValidationErrors(err.detail);
  const lower = raw.toLowerCase();

  if (status === 401) {
    return {
      title: "Incorrect sign-in details",
      message: "The email or password you entered doesn't match any account.",
      fieldErrors: {
        email: "Check that your email is correct.",
        password: "Check that your password is correct.",
      },
      hint: "If you don't have an account yet, switch to Register below.",
    };
  }

  if (status === 409 || lower.includes("already registered")) {
    return {
      title: "Account already exists",
      message: "An account with this email is already registered.",
      fieldErrors: { email: "This email is taken. Try signing in instead." },
      hint: "Switch to Log in if you already have an account.",
    };
  }

  if (status === 422 || Object.keys(fieldErrors).length > 0) {
    const firstField = (Object.keys(fieldErrors)[0] as AuthField) || null;
    return {
      title: "Please fix the highlighted fields",
      message: firstField
        ? fieldErrors[firstField] || "Some details are invalid or missing."
        : "Some details are invalid or missing.",
      fieldErrors,
    };
  }

  if (status === 429) {
    return {
      title: "Too many attempts",
      message: "Please wait a moment before trying again.",
      fieldErrors: {},
    };
  }

  if (status >= 500) {
    return {
      title: "Server unavailable",
      message: "Our servers are having trouble right now. Please try again in a few minutes.",
      fieldErrors: {},
    };
  }

  return {
    title: mode === "login" ? "Sign in failed" : "Registration failed",
    message: raw || "Something went wrong. Please try again.",
    fieldErrors,
  };
}

export function validateAuthForm(
  mode: "login" | "register",
  values: { email: string; password: string; name: string },
): AuthFormFeedback | null {
  const fieldErrors: Partial<Record<AuthField, string>> = {};
  const email = values.email.trim();

  if (!email) {
    fieldErrors.email = "Email is required.";
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    fieldErrors.email = "Enter a valid email address (e.g. you@example.com).";
  }

  if (!values.password) {
    fieldErrors.password = "Password is required.";
  } else if (values.password.length < 6) {
    fieldErrors.password = "Password must be at least 6 characters.";
  }

  if (mode === "register" && values.name.trim().length > 120) {
    fieldErrors.name = "Name is too long (maximum 120 characters).";
  }

  if (Object.keys(fieldErrors).length === 0) return null;

  return {
    title: "Please fix the highlighted fields",
    message: "Check the fields marked below before continuing.",
    fieldErrors,
  };
}
