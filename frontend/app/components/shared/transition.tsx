export default function TransitionLayer() {

  const col1 = "#726FA6"
  const col2 = "#3F3D63"
  const col3 = "#23223D"
  const col0 = "#9F9BD2"
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
