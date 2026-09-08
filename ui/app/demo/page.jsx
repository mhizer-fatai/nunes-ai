import Link from "next/link";
import Nav from "../components/Nav";
import { ScrollProgress } from "../components/Motion";
import DemoConsole from "../components/DemoConsole";

export default function DemoPage() {
  return (
    <>
      <ScrollProgress />
      <Nav
        cta={
          <Link className="btn btn-ghost btn-sm" href="/app">
            Back to workspace
          </Link>
        }
      />
      <div className="wrap demo-screen">
        <div className="demo-head">
          <div className="eyebrow">Guided demo · the load-bearing moment</div>
          <h1>Watch memory say no.</h1>
          <p>
            A team of three agents shares one persistent Sibyl Memory. This console runs the real
            guard — not a mock — against a throwaway database: a payment settles, a fresh process
            tries the same invoice and is refused, a banned vendor is refused, and then the memory
            is deleted and the exact same request sails through. Settlement is forced to
            simulation, so nothing here broadcasts funds.
          </p>
        </div>
        <DemoConsole />
      </div>
    </>
  );
}
