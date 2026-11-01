import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useMe } from "./api";
import { Loading } from "../../components/ui/Spinner";

/**
 * Gate for every route but /login. The pending state must render *something*
 * neutral rather than redirecting: on a hard refresh `me` is always pending for
 * a moment, and bouncing to /login there would log the user out on every reload.
 */
export function ProtectedRoute() {
  const { data, isPending, isError } = useMe();
  const location = useLocation();

  if (isPending) {
    return (
      <div className="grid min-h-dvh place-items-center px-4">
        <Loading />
      </div>
    );
  }

  if (isError || !data) {
    // `from` lets login send the user back where they were headed.
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <Outlet />;
}
