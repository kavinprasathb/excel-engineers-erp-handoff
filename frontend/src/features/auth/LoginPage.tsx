import { useState } from "react";
import type { FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useLogin, useMe } from "./api";
import { Button } from "../../components/ui/Button";
import { FormField } from "../../components/ui/FormField";
import { Input } from "../../components/ui/Input";
import { Icon } from "../../components/ui/Icon";
import { errorMessage } from "../../lib/errors";
import { isApiError } from "../../api/client";
import { errorCardCls } from "../../components/ui/styles";
import { FooterIcon } from "./LoginArt";

interface LocationState {
  from?: string;
}

const PROMISES = [
  { icon: "gear", title: "German Engineering", sub: "Superior Quality" },
  { icon: "shield", title: "Reliable Performance", sub: "Longer Life" },
  { icon: "leaf", title: "Sustainable Solutions", sub: "for a Better Tomorrow" },
] as const;

/**
 * The front door: a dealer header, a blue hero with a pump set and a frosted
 * sign-in card at its centre, and a navy band of promises underneath.
 */
export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { data: me, isPending: mePending } = useMe();
  const login = useLogin();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [touched, setTouched] = useState(false);

  const from = (location.state as LocationState | null)?.from ?? "/inventory";

  // Someone with a live session should never be looking at this form.
  if (!mePending && me) return <Navigate to={from} replace />;

  const emailError = touched && !email.trim() ? "Enter your email address." : undefined;
  const passwordError = touched && !password ? "Enter your password." : undefined;

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setTouched(true);
    if (!email.trim() || !password) return;

    login.mutate(
      { email: email.trim(), password },
      { onSuccess: () => navigate(from, { replace: true }) },
    );
  }

  const failure = login.error;
  const failureText = failure
    ? isApiError(failure) && failure.code === "invalid_credentials"
      ? "That email and password do not match an account."
      : errorMessage(failure)
    : null;

  return (
    <main className="flex min-h-dvh flex-col bg-app-bg">
      <header className="relative z-10 border-b border-[#d6e2f2] bg-[#f3f7fc] shadow-[0_2px_12px_-6px_rgba(11,45,107,0.25)]">
        <div className="mx-auto flex max-w-[1400px] items-center gap-4 px-4 py-4 sm:min-h-[100px] sm:gap-6 sm:px-8">
          <img
            src="/logo-excel-ksb.png"
            alt="Excel Engineers, KSB Authorized Dealer"
            width={450}
            height={100}
            className="h-12 w-auto sm:h-[68px]"
          />
          <p className="ml-auto hidden border-l border-line pl-5 text-[13px] font-medium leading-snug text-[#1f4f9a] md:block">
            Engineering Excellence
            <br />
            with Trusted Solutions
          </p>
        </div>
      </header>

      <section
        className="relative flex flex-1 items-center justify-center overflow-hidden bg-[#123f86] bg-cover bg-[position:65%_center] px-4 py-10 sm:py-16"
        style={{ backgroundImage: "url(/login-bg.jpg)" }}
      >
        {/* Tint the photo into the brand blues, darker at the edges, so the card reads. */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "linear-gradient(120deg, rgba(8,34,84,0.78) 0%, rgba(16,63,140,0.55) 45%, rgba(18,72,160,0.35) 70%, rgba(8,34,84,0.55) 100%)",
          }}
        />
        <div className="relative w-full max-w-[420px] rounded-2xl bg-card/85 p-6 shadow-[0_30px_60px_-20px_rgba(5,20,50,0.6)] ring-1 ring-white/40 backdrop-blur-xl sm:p-8">
          <h1 className="text-center font-display text-[26px] font-extrabold tracking-tight text-logo">Dealer Login</h1>
          <p className="mt-1 text-center text-[14px] text-ink-2">Access your account to continue</p>

          <form onSubmit={onSubmit} noValidate className="mt-6 space-y-5">
            {failureText ? (
              <div className={errorCardCls} role="alert">
                <div className="flex items-start gap-2">
                  <Icon name="alert" className="mt-0.5 text-red" />
                  <p className="text-[13px] text-red">{failureText}</p>
                </div>
              </div>
            ) : null}

            <FormField label="Email" required error={emailError}>
              {(props) => (
                <div className="relative">
                  <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-ink-2">
                    <Icon name="user" size={17} />
                  </span>
                  <Input
                    {...props}
                    type="email"
                    name="email"
                    autoComplete="username"
                    autoFocus
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Email address"
                    className="h-11 pl-10"
                  />
                </div>
              )}
            </FormField>

            <FormField label="Password" required error={passwordError}>
              {(props) => (
                <div className="relative">
                  <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-ink-2">
                    <Icon name="lock" size={17} />
                  </span>
                  <Input
                    {...props}
                    type={show ? "text" : "password"}
                    name="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Password"
                    className="h-11 pl-10 pr-16"
                  />
                  <button
                    type="button"
                    onClick={() => setShow((s) => !s)}
                    aria-pressed={show}
                    className="absolute inset-y-0 right-0 px-3 text-[12.5px] font-medium text-ink-2 transition-colors hover:text-ink"
                  >
                    {show ? "Hide" : "Show"}
                  </button>
                </div>
              )}
            </FormField>

            <Button
              type="submit"
              variant="primary"
              fullWidth
              loading={login.isPending}
              className="h-11 !bg-[#0b2d6b] text-[14.5px] shadow-[0_8px_20px_-8px_rgba(11,45,107,0.7)] hover:!bg-[#133f8f]"
            >
              Login <span aria-hidden="true">→</span>
            </Button>
          </form>

          <p className="mt-6 flex items-center gap-2 text-[12px] text-ink-2">
            <Icon name="lock" size={13} />
            Secure sign-in. Ask the owner if you need an account.
          </p>
        </div>
      </section>

      <footer className="bg-[#081f4d] text-white">
        <ul className="mx-auto grid max-w-[1100px] grid-cols-1 gap-4 px-6 py-5 sm:grid-cols-3 sm:gap-0 sm:divide-x sm:divide-white/20">
          {PROMISES.map((p) => (
            <li key={p.title} className="flex items-center gap-3 sm:justify-center sm:px-4">
              <FooterIcon name={p.icon} />
              <span className="leading-tight">
                <span className="block font-display text-[14px] font-bold">{p.title}</span>
                <span className="block text-[12.5px] text-white/70">{p.sub}</span>
              </span>
            </li>
          ))}
        </ul>
      </footer>
    </main>
  );
}
