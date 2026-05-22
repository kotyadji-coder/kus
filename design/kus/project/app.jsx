// Mount: two artboards in a design canvas — desktop + mobile.

const { createRoot: createCanvasRoot } = ReactDOM;

const Mount = () => (
  <DesignCanvas>
    <DCSection
      id="landing"
      title="Кусь · Подбор рациона"
      subtitle="Лендинг doggi.ru/food — два размера для предпросмотра"
    >
      <DCArtboard id="desktop" label="Desktop · 1440px" width={1440} height={8500}>
        <Landing mobile={false} />
      </DCArtboard>
      <DCArtboard id="mobile" label="Mobile · 390px" width={390} height={11400}>
        <Landing mobile={true} />
      </DCArtboard>
    </DCSection>
  </DesignCanvas>
);

createCanvasRoot(document.getElementById('root')).render(<Mount />);
