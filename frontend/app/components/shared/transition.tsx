export default function TransitionLayer() {

  const col1 = "#5E2C32"
  const col2 = "#893F47"
  const col3 = "#BF5864"
  return (
    <>

      {/* <div id="transitionCircle0" className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2  */}
      {/*           rounded-full w-[1px] h-[1px] scale-none z-50" */}
      {/*   style={{ */}
      {/*     background: col0 */}
      {/*   }}> */}
      {/* </div > */}
      <div id="transitionCircle1" className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full w-[1px] h-[1px] scale-none z-50"
        style={{
          background: col1
        }}>
      </div >


      <div id="transitionCircle2" className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full w-[1px] h-[1px] scale-none z-50"
        style={{
          background: col2
        }}>
      </div >


      <div id="transitionRing" className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full outline-[0px] w-[1px] h-[1px] scale-none z-51"
        style={{
          outlineColor: col3,
          background: col3
        }}>
      </div >
    </>
  )
}
